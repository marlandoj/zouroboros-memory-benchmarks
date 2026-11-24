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

It is applied uniformly to every task; it never touches grading, checks, the judge, the
transcript, or the app state; and a call that differs in any non-null value still fails the
guard. Benchmark code is not modified.

## Changes in this persisted copy relative to the first run (adapter 0.3.0)

Behaviour the agent and the grader see is unchanged: same plugin bytes, same profile
templates, same toolsets, same model settings, same repair. What changed:

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
