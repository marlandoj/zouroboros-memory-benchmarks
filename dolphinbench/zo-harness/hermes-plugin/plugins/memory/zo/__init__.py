"""Zouroboros memory plugin using the MemoryProvider interface.

Configuration lives in ``$HERMES_HOME/zo.json``::

    {"base_url": "http://127.0.0.1:8764", "identity": "morgan"}

The base URL is the Zouroboros DolphinBench adapter server
(packages/memory/src/dolphinbench/server.ts), which owns the persona's frozen
scratch SQLite store. The store is ingested directly by the adapter (every
history message with its timestamp) and locked before the task phase, so this
plugin never writes: ``sync_turn`` is a no-op and there is no prefetch —
Hermes adds a provider's prefetch to the user's message itself, and
DolphinBench's submission format requires that message unchanged, so the
system prompt asks the agent to recall first.

Standard library only, so the plugin needs nothing beyond Hermes itself.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider
from tools.registry import tool_error

logger = logging.getLogger(__name__)

# One recall page: at most 20 results; each excerpt is capped so the JSON
# stays well under Hermes' tool-result preview limits.
RECALL_LIMIT = 20
RECALL_EXCERPT_MAX_CHARS = 1_500
RECALL_TIMEOUT_SECONDS = 30
RETRY_DELAYS_SECONDS = (1, 2, 4)

RECALL_SCHEMA = {
    "name": "zo_recall",
    "description": (
        "Search your long-term memory of the user (Zouroboros) for what was said in earlier "
        "conversations. Write one short, specific query naming the person, project, decision, "
        "date, number or wording that identifies the fact you need; call zo_recall again for "
        "each further fact, at most three calls at once. Returns dated excerpts of the earlier "
        "conversations."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "One short, specific query for one fact."},
        },
        "required": ["query"],
    },
}


def load_config(hermes_home: str) -> dict:
    home = Path(hermes_home)
    candidates = [home / "zo.json"]
    # Inside the benchmark's agent container only the active profile is staged
    # under $HERMES_HOME/profiles/, so the profile copy carries the config.
    profiles = home / "profiles"
    if profiles.is_dir():
        candidates.extend(sorted(profiles.glob("*/zo.json")))
    for path in candidates:
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("zo: %s is not valid JSON", path)
            continue
        if isinstance(value, dict) and value.get("base_url"):
            return value
    return {}


class ZoClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def recall(self, query: str, timeout: float) -> dict:
        body = {"query": query, "limit": RECALL_LIMIT}
        data = json.dumps(body).encode("utf-8")
        for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
            last = attempt == len(RETRY_DELAYS_SECONDS)
            request = urllib.request.Request(
                self._base_url + "/recall", data=data, method="POST",
                headers={"Content-Type": "application/json", "Accept": "application/json"})
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    raw = response.read()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as error:
                if (error.code == 429 or error.code >= 500) and not last:
                    time.sleep(RETRY_DELAYS_SECONDS[attempt])
                    continue
                detail = error.read().decode("utf-8", "replace")[:300]
                raise RuntimeError(f"zo /recall returned {error.code}: {detail}") from error
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                if last:
                    raise
                time.sleep(RETRY_DELAYS_SECONDS[attempt])
        raise AssertionError("unreachable")


class ZoMemoryProvider(MemoryProvider):
    def __init__(self) -> None:
        self._config: dict = {}
        self._client: Optional[ZoClient] = None

    @property
    def name(self) -> str:
        return "zo"

    def is_available(self) -> bool:
        from hermes_constants import get_hermes_home
        config = load_config(str(get_hermes_home()))
        return bool(config.get("base_url"))

    def unavailable_reason(self) -> str:
        return "Write base_url to $HERMES_HOME/zo.json"

    def initialize(self, session_id: str, **kwargs) -> None:
        from hermes_constants import get_hermes_home
        hermes_home = kwargs.get("hermes_home") or str(get_hermes_home())
        self._config = load_config(hermes_home)
        self._client = ZoClient(str(self._config["base_url"]))

    def system_prompt_block(self) -> str:
        return (
            "Your long-term memory of the user is Zouroboros. Call zo_recall first whenever a "
            "request depends on anything from earlier conversations: people, projects, decisions, "
            "preferences, instructions, dates, numbers, commitments or exact wording. It returns "
            "dated excerpts of those conversations. Ask for each fact with a short, specific "
            "query, one query per call, calling it again for each further fact, and recall again "
            "with narrower or different words if the results do not hold what you need."
        )

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        # Ingestion is adapter-side and the store is frozen before the task
        # phase; the agent never writes memory in this configuration.
        return

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [RECALL_SCHEMA]

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if tool_name != "zo_recall":
            return tool_error(f"Unknown tool: {tool_name}")
        if self._client is None:
            return tool_error("Zouroboros memory is not configured")
        query = args.get("query")
        if query is None and isinstance(args.get("queries"), list) and len(args["queries"]) == 1:
            query = args["queries"][0]
        if isinstance(args.get("queries"), list) and len(args["queries"]) > 1:
            return tool_error("Send one query per zo_recall call")
        if not isinstance(query, str) or not query.strip():
            return tool_error("Missing required parameter: query")
        try:
            page = self._client.recall(query.strip(), RECALL_TIMEOUT_SECONDS)
        except Exception as error:
            logger.warning("zo recall failed: %s", error)
            page = {"error": f"zo recall failed: {str(error)[:300]}", "results": []}
        results = []
        for item in (page.get("results") or [])[:RECALL_LIMIT]:
            text = str(item.get("text") or "")
            if len(text) > RECALL_EXCERPT_MAX_CHARS:
                text = text[:RECALL_EXCERPT_MAX_CHARS].rsplit(" ", 1)[0] + " …"
            results.append({
                "date": item.get("narrativeDate"),
                "session": item.get("sessionId"),
                "score": round(float(item.get("score") or 0.0), 4),
                "excerpt": text,
            })
        return json.dumps({"query": query.strip(), "results": results}, ensure_ascii=False,
                          separators=(",", ":"))


def register(ctx) -> None:
    ctx.register_memory_provider(ZoMemoryProvider())
