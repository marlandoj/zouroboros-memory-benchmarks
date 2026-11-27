# zo-harness — Zouroboros memory for the DolphinBench reference agent

This directory is the harness side of the DolphinBench x Zouroboros smoke evaluations:
the Hermes memory plugin the agent uses, the runner adapter that plugs Zouroboros into the
benchmark's own Runner (including one disclosed evidence repair), the model relays, and the
scripts that run a smoke detached and without credentials in any log. The memory adapter
itself (ingest, recall, freeze, checkpoint) is not here: it is
`packages/memory/src/dolphinbench/` in marlandoj/zouroboros-workspace (PR #1114, merged).

No dataset content is in this directory, and none is written into it by a run: every run
output lives in the run directory named by `run.conf` (outside any repository).

## Provenance

| Path | Origin |
|---|---|
| `hermes-plugin/plugins/memory/zo/` | Written for the first smoke (2026-11-23, card t_baa4f1d6) and committed on top of the reference Hermes in a local, never-pushed checkout (`hermes-reference`, commit 6c06a3a). Byte-identical here (SHA-256 `e1c45d3a…` `__init__.py`, `f4483200…` `plugin.yaml`). |
| `runner/zo_harness.py` | Written for the first smoke. The first commit of this directory is the exact file that run executed (SHA-256 `10c21791…`, the `adapter_source_sha256` in that run's `run.json`, adapter 0.2.0). The next commit makes it 0.3.0 (see below). |
| `runner/run_smoke.py` | Written for the first smoke; first commit verbatim, then parametrised (see below). |
| `runner/agent_relay.py`, `runner/judge_relay.py` | Copied from pastdotdev/benchmarks `dolphin/` @ b3971de (MIT, Copyright (c) 2026 Past Corp). The judge relay is unchanged; the agent relay's authentication is changed (see below). |
| `runner/export_history.py` | Written for the first smoke; unchanged. |
| `scripts/` | New with this directory (remediation card t_f7832f7b, 2026-11-24). |

The reference agent is DolphinBench's pinned configuration: NousResearch/hermes-agent @
935c1e8 plus the release's `examples/reference/hermes-evaluation.patch` (DolphinBench @
81cb6f8). `scripts/prepare_hermes_source.sh` builds that source as two commits — the patch
(its SHA-256 must equal the release spec's `patch_sha256`), then this directory's plugin — so
the image and the controller-side Hermes run the persisted plugin, not an untracked copy.
`run_smoke.py` refuses to run if the source's plugin differs from `hermes-plugin/`, and
`zo_harness.py` (as in the first run) refuses a source that differs from the reference
anywhere outside `plugins/memory/zo`.

## The plugin

`plugins/memory/zo` registers a Hermes `MemoryProvider` named `zo` with one tool,
`zo_recall(query)`, which POSTs `{query, limit: 20}` to the Zouroboros adapter server's
`/recall` (hybrid search over the frozen persona store) and returns dated excerpts (each
capped at 1,500 chars). It never writes: `sync_turn` is a no-op and there is no prefetch,
because Hermes would add prefetch text to the user message and DolphinBench requires that
message unchanged. Standard library only.

## The disclosed app-call repair (`ZoHermesAdapter._repair_app_call_args`)

What goes wrong without it. DolphinBench's submission guard
(`harness/submission.py`, `grading_calls`) requires every app call the adapter reports to
match a tool call in the conversation transcript exactly (tool name plus JSON arguments).
The release's mock app server logs *enriched* arguments — optional parameters the model did
not send appear with their `null` defaults (for example `"cc": null` on an email send) —
while the transcript records the model's raw arguments, which omit them. The guard then
raises `SubmissionError` and the whole run aborts on a representation difference that says
nothing about what the agent did. In the first smoke this hit task 005 twice.

What the repair does, exactly, for each test-phase interaction after the agent finishes:

1. Take the transcript's tool calls (`check_messages(record.messages, "transcript")`).
2. Define `drop_nulls(v)`: recursively remove every dict key whose value is `None`
   (lists are walked element by element; nothing else is changed).
3. For each app call the adapter reports, in order:
   - if it matches an unused transcript call exactly, it is left untouched;
   - else, if `[tool, drop_nulls(args)]` equals `[tool, drop_nulls(transcript_args)]` for an
     unused transcript call, its `args` are replaced by `drop_nulls(args)` — i.e. only the
     null-valued keys are removed, nothing is added or altered;
   - else it is left as is, so the benchmark's guard still rejects it and the run aborts.
4. Every repaired call is appended to `<output>/app-call-repairs.json` under its task id, as
   `{"tool": ..., "dropped_null_keys": [...]}`.

**Second rule (adapter 0.4.0, added during the 2026-11-24 remediation re-run, disclosed).**
The server fills an *omitted* optional parameter with its declared default even when that
default is not null: `list_open_prs(..., status="open")`. In the re-run, Luna sent
`status: null` (allowed by the tool's docstring). Hermes's tool-call wrapper rejected that
on argument validation, so the model re-sent the call without `status`, and the server logged
`status: "open"`. The null rule cannot match that, so the guard aborted grading of task 021
on three consecutive fresh attempts (and task 019 once). The second rule runs only after the
exact and null rules fail. It drops an app-log key only when (a) the transcript call lacks
the key, (b) its value is non-null, and (c) the value equals the literal default that the
release's own server code declares for that tool and parameter. The default is read with
`ast` from `mock_mcp/repair_*.py`'s `Candidate*` classes, falling back to
`mock_mcp/server.py`, in `build_server`'s lookup order. After the drop, the same exact
post-null-drop match must hold, or the guard still aborts. Repairs are logged with
`"rule": "declared-default"` and `"dropped_default_keys"`. An offline replay over every
saved evidence file of both smoke runs shows the rule changes nothing in any evidence
the guard already accepts (45 files) and repairs exactly the 4 crashed attempts
(`tools/repair_replay.py` in the remediation card).

It is applied uniformly to every task; it never touches grading, checks, the judge, the
transcript, or the app state; and a call that differs in any non-null value still fails the
guard. Benchmark code is not modified.

**Third rule (adapter 0.5.0, added during the 2026-11-24 full run, disclosed).** The server
coerces a number to its parameter's declared type before logging it: the model sends
`max_price_usd: 900`, the app log records `900.0`, and the guard's JSON key tells the two
apart. In the full run's Morgan leg (adapter 0.4.0) this aborted grading of task 129 on the
original attempt and both fresh re-runs (bound reached). The rule runs only after the exact,
null and declared-default rules fail. For a transcript call of the same tool, after the same
null and declared-default drops, it replaces an app-log number by the transcript's number at
the same key path when the two are numerically equal and differ only in int/float type
(bools excluded); then the same exact post-repair match must hold, or the guard still aborts.
Repairs are logged with `"rule": "numeric-representation"` and `"retyped_keys"`. Offline
replay (`scripts/repair_replay.py`) over 180 saved evidence files (both smoke runs, the
full run's 0.4.0 Morgan attempt and its quarantined attempts): the 173 the guard already
accepts are unchanged with zero repairs; all 7 crashed attempts now pass (the 3 task-129
attempts via this rule, the 4 smoke attempts via the declared-default rule as before).
Because the adapter identity changed, the full run restarted Morgan from a fresh run
directory under 0.5.0; the 0.4.0 attempt is preserved, not merged into the result.

## Full run (`scripts/full_run.sh`)

`run_smoke.py` takes the persona and test count from `run.conf` (`ZO_BENCH_PERSONA`,
`ZO_TEST_COUNT=all`; with neither set, the smoke's run identity is unchanged).
`scripts/full_run.sh <cap USD> <run.conf>...` runs personas one after another, one run
directory each, every stage a `systemd --user` unit; it checks cumulative cash every 60 s
during evaluate (stopping at the cap), writes a projection from the first persona's measured
rates (`scripts/full_cost.py`) and stops if it exceeds the cap, and applies the smoke's
guard-crash policy (quarantine + fresh re-run, at most 2 re-runs per task) automatically.
Launch it detached:

```
systemd-run --user --collect --unit=<name> -p StandardOutput=append:<log> \
  /bin/bash scripts/full_run.sh 50 <morgan.conf> <alex.conf> <riley.conf>
```

## Production-parity ingest arm (adapter 0.6.0, 2026-11-25)

A separate arm, reported against the direct-ingest baseline (0.5.0, 428/600), not a repair.
The ingest stage keeps the 0.5.0 verbatim pass (one fact + one episode per message) and adds
two adapter stages before freeze, both reusing exported production functions unchanged
(zouroboros-workspace `packages/memory/src/dolphinbench/adapter.ts`):

- **Extraction** (`/extract`): each session's message is one chunk run through the memory
  package's exported capture extraction (`capture.ts` `extractFromText`, the extractor behind
  `autoCapture`). Extracted facts are stored through `storeFact` with their own entity/key/value
  and autoCapture's parameters (decay `stable`, importance 1.5 for decisions), metadata
  `layer: extracted`, session id and narrative date, `created_at` rewound to the narrative date.
  That extractor is heuristic (pattern-based) and makes no model call: the recorded extractor
  model is `null`. The model-backed extractor (`standalone/auto-capture.ts`, model-client
  workload `extraction`) is a private function of a CLI script and is not reusable as exported;
  it is not forked here. Failed chunks are rolled back, counted and listed in
  `hermes/accounting/extraction-failures.json`; more than 5% failed chunks stops the stage.
- **Consolidation** (`/consolidate`): `consolidateObservations` for the persona with the
  production defaults (`minProof` 2, `useLlm` false).
- **Recall union**: `/recall` merges `searchObservations` beliefs into the `searchFactsHybrid`
  page under the adapter's `RECALL_MERGE_RULE`: beliefs first, at most a quarter of the page
  (5 of 20), a belief dropped when its newest supporting fact is already on the page, facts
  never dropped for a belief. Extracted-fact excerpts are labelled `entity[.key]: value`. The
  plugin is unchanged (dated excerpts capped at 1,500 chars).
- **Freeze**: checkpoint v3 hashes observations and their evidence links too; the fresh-process
  verification covers them.
- `ingestion.json` itemises the three legs (`legs.verbatim|extraction|consolidation`), and
  `costs.py` prints them as `ingest_legs`. `run_smoke.py` refuses an adapter server that does
  not report version 0.6.0.

## Changes in this persisted copy relative to the first run (adapter 0.3.0)

Behaviour the agent and the grader see is unchanged: same plugin bytes, same profile
templates, same toolsets, same model settings. The null-key repair is unchanged; 0.4.0 adds
the declared-default rule described above. What else changed:

- **Credentials never reach a log.** The benchmark's container launcher passes the agent's
  provider variables as `docker create --env NAME=VALUE` arguments and allows
  `OPENAI_API_KEY` for every agent; in the first run the host key was in the runner's
  environment, so an error dump of that command wrote it into a log. Now:
  - `run_smoke.py` refuses to start if any provider credential (or any credential-shaped
    value) is in its environment;
  - the zo adapter server gets `OPENAI_API_KEY` only through `bun --env-file=<0600 file>`;
  - the relays get `OPENROUTER_API_KEY` only through systemd `EnvironmentFile=`;
  - the env-files live on tmpfs (`/run/user/<uid>/…`, mode 0700/0600), are written with a
    shell builtin (no command line carries a value), and are deleted after the run;
  - the agent relay no longer has a shared password. For each interaction the harness mints
    a random token, registers only its SHA-256 (file `relay-tokens/<hash>`, content = the
    interaction tag), passes `<token>.<tag>` to the container, and deletes the registration
    when the interaction ends. A token is therefore a single-interaction capability, dead
    afterwards, and never a provider key;
  - the judge relay password is random per run, held only by the judge relay and the
    runner's judge client, and unset for every agent interaction;
  - `scripts/scan_logs.py` scans every file the run produced for the exact secret values,
    for any issued relay token (by hash), and for credential-shaped strings, printing counts
    and paths only.
- **Detached execution.** `scripts/launch.sh` starts the relays and each stage as transient
  `systemd --user` units (`systemd-run --user --collect`). They belong to the user manager,
  not to the caller's session, process group or cgroup, so a caller's timeout or reap
  cannot kill them. The relays restart on failure.
- **Paths from `run.conf`.** One copy serves any run directory; see `run.conf.example`.
- `freeze` also verifies the new checkpoint once from a fresh, locked server process (the
  task-phase configuration), and a `summary` stage writes aggregate per-task check counts.
- **Embedder recorded, not assumed.** The first run's ingest record hard-coded
  `text-embedding-3-small`; the model and its list price now come from the store. Note:
  zouroboros-workspace main's production embedder has been `text-embedding-3-large` (3072)
  since 2026-11-09; the first smoke embedded with 3-small only because its intelligence
  `dist` was stale. `run.conf` can pin the embedder for a DolphinBench scratch store
  (`ZO_DOLPHINBENCH_EMBEDDING_MODEL` / `_DIMENSION`, zouroboros-workspace PR #1115).

## Running a smoke

```
cp run.conf.example /path/to/run.conf            # edit paths
ZO_SECRETS_DIR=/run/user/$(id -u)/<run> bash scripts/write_env_files.sh
bash scripts/prepare_hermes_source.sh /path/to/run.conf
bash scripts/launch.sh /path/to/run.conf image   # poll: logs/image-build.log
bash scripts/launch.sh /path/to/run.conf relays
bash scripts/launch.sh /path/to/run.conf stage prepare   # then ingest, freeze, evaluate, summary
# poll logs/<stage>.log and logs/<stage>.exit
bash scripts/launch.sh /path/to/run.conf stop
python scripts/scan_logs.py <run dir> --secrets <secrets dir>
# then delete the secrets dir
```

Host prerequisites from the first run still apply: the user is in the `docker` group (the
scripts use `sg docker`), and the host firewall must accept docker0 -> host on 8764 (zo
server) and 8766 (agent relay).

## Out of scope

The route: the reference harness has no openai-codex (ChatGPT subscription) provider, so the
agent runs OpenRouter `openai/gpt-5.6-luna` pinned to its Azure provider through the agent
relay, and the judge runs `gpt-5.6-sol` medium through the judge relay, same pinning.
Building a subscription provider would deviate from the published configuration.
