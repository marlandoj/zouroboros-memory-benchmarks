# DolphinBench — Zouroboros memory, full run (2026-11-24)

Commissioned by Marlando, 2026-11-24. Run by three factory cards in turn (t_8f00fc5b original,
t_b68d5563 continuation, t_b6af091e closing); this report and its cost reconstruction were
done by a fourth (t_ebd974b8), which did no evaluation, no re-grading and no adapter change.
**Aggregate results only:** no dataset rows, histories, dialogue, app state, task text or judge
text appear here.

## Outcome

All 600 tasks were graded (200 per persona). The run went through four incidents on the way,
all set out in full below: a systematic guard abort that forced an adapter repair and a Morgan
restart, a full root disk that killed Alex's first evaluation, an outage of the pinned agent
provider that stopped Riley's first evaluation, and session timeouts on two of the cards. The
detached driver finished the run at 2026-11-25T03:14:49Z.

| Persona | Tasks fully passed | Checks passed | Judge-called checks passed |
|---|:---:|:---:|:---:|
| Morgan Chen | **156 / 200 (78.0%)** | **457 / 591 (77.3%)** | 147 / 178 |
| Alex | **128 / 200 (64.0%)** | **482 / 719 (67.0%)** | 131 / 188 |
| Riley | **144 / 200 (72.0%)** | **462 / 610 (75.7%)** | 164 / 213 |
| **Pooled** | **428 / 600 (71.3%)** | **1,401 / 1,920 (73.0%)** | 442 / 579 |

**Read every number in this report with the ingestion deviation below.** This run ingested the
histories directly through the adapter. The published rows used agent-mediated ingestion. So
the scores are not like-for-like with the published field, and neither are the costs.

Cash: **USD 8.745864** for the whole run, superseded attempt included. The cap was USD 50, so
the run used 17.5% of it. One bounded residual is not itemised: query-time embeddings at
recall, ≤ USD 0.041 (see Costs).

## Configuration as run

- **Benchmark:** mem0ai/dolphinbench @ 81cb6f8. Its grading and its judge are unchanged.
- **Memory:** the Zouroboros DolphinBench adapter (`packages/memory/src/dolphinbench`) on
  zouroboros-workspace main @ f36ebda6. It ran on the persisted zo harness from this repo
  (`dolphinbench/zo-harness/`, PR #4) at **adapter 0.5.0** (zo_harness.py SHA-256
  0d7d52a7…; see the incident account for the mid-run 0.4.0 → 0.5.0 repair). The harness
  commits on top of PR #4 that the run used (349d802 full-run driver, 094bed4 adapter 0.5.0,
  ead1c18 tolerant cap-check parser) are part of this PR.
- **Embedder:** the production `text-embedding-3-large` (3072-d). No pin.
- **Agent:** the Hermes Agent reference build (binary a64af575…, image
  sha256:9cc5cae7…), GPT-5.6 Luna, reasoning high, max 60 turns, benchmark retry
  environment `DOLPHINBENCH_TEST_RETRIES=3`. Toolsets: `dolphinbench-apps`, `memory` (the zo
  plugin: `zo_recall` only, so the agent never writes memory) and `session_search`.
- **Judge:** GPT-5.6-Sol, medium. All 581 judge calls in the result directories were served
  by Azure.
- **Route:** the reference harness has no subscription (openai-codex) provider, so the agent
  and the judge went through OpenRouter, pinned to the Azure provider, fallbacks off, via
  local relays.
- **Execution:** personas ran one after another (Morgan, Alex, Riley). Each stage ran as a
  detached `systemd --user` unit. Every persona was ingested in full (3,400 / 5,011 / 5,128
  history messages, none skipped), frozen under the v2 content-hash checkpoint, and evaluated
  on all 200 of its tasks in benchmark order.

### Ingestion deviation (read this alongside every number)

**This run ingested each persona's history directly through the adapter.** Every message,
with its timestamp, was stored as a fact, an episode and an embedding. No agent filtered or
summarised anything at write time. **The published Hermes + Luna rows used agent-mediated
ingestion:** the agent reads the history and decides what to store.

What this does to the score: direct ingestion can help recall (nothing is dropped) or hurt
it (no salience filtering, more distractors at retrieval). This run does not measure the size
or the sign of that effect.

What it does to the cost: under direct ingestion, ingestion cost only embeddings, USD
0.0665–0.0675 per persona (0 agent calls in the ingestion phase, in all four run
directories).
Under agent-mediated ingestion, the agent would also have to read 3,400–5,128 history
messages per persona through Luna. This run has no record from which to price that, so the
costs below cover memory build plus evaluation under direct ingestion. They are not an
estimate of what a published-row configuration would cost.

## Results

### Against the published Hermes + Luna field (600 tasks, agent-mediated ingestion)

| System | Tasks passed (of 600) | Rate |
|---|:---:|:---:|
| past.dev | 490 | 81.7% |
| **Zouroboros (this run, direct ingestion)** | **428** | **71.3%** |
| Mem0 | 424 | 70.7% |
| Hindsight | 417 | 69.5% |
| Honcho | 411 | 68.5% |
| Hermes built-in | 394 | 65.7% |
| Supermemory | 355 | 59.2% |

How to read this:
- **Ingestion differs** (above). The placement shows where the number falls. It is not a
  like-for-like rank.
- **Small margins.** The 4-task margin over Mem0, and the margins to the rows just below
  it, are smaller than the effects this run cannot rule out:
  - the ingestion difference;
  - run-to-run variation. On the 128 Morgan tasks that both the 0.4.0 attempt and the 0.5.0
    result graded, 115 had identical check vectors, and 97 vs 98 tasks passed.
- **Personas differ in difficulty:** Morgan 78.0%, Riley 72.0%, Alex 64.0%. The published
  per-persona split is not available to compare against.

### Per-kind split (the benchmark's grader types, per check)

| Check type | Morgan | Alex | Riley | Pooled |
|---|:---:|:---:|:---:|:---:|
| field_equals | 281 / 362 | 324 / 477 | 269 / 355 | 874 / 1,194 |
| field_llm_judge | 147 / 187 | 131 / 201 | 164 / 222 | 442 / 610 |
| datetime_absolute_eq | 4 / 6 | 19 / 31 | 20 / 24 | 43 / 61 |
| field_eq_number | 11 / 12 | — | — | 11 / 12 |
| field_list_includes | 5 / 7 | 5 / 6 | — | 10 / 13 |
| field_absent_or_empty | — | — | 7 / 7 | 7 / 7 |
| field_list_equals_unordered | 3 / 3 | 0 / 1 | 1 / 1 | 4 / 5 |
| field_regex | 3 / 5 | — | — | 3 / 5 |
| field_markdown_bullets | 0 / 4 | — | — | 0 / 4 |
| tool_called | 1 / 1 | 3 / 3 | — | 4 / 4 |
| tool_success_count | 2 / 3 | — | — | 2 / 3 |
| date_on | — | — | 1 / 1 | 1 / 1 |
| field_equals_all_calls | 0 / 1 | — | — | 0 / 1 |

Two sets of counts differ, both by the benchmark's design:
- **`field_llm_judge` checks vs judge calls.** The judge was called on 178 / 188 / 213 checks,
  fewer than the `field_llm_judge` totals. The benchmark grades per action, and an action
  whose deterministic assertions already fail is not sent to the judge.
- **Judge-called checks vs judge answers.** Every judge relay call ties to one recorded judge
  answer in a standing grade file: Morgan 178 = 178, Alex 189 = 189, Riley 214 = 214.
  Answers exceed judge-called checks for Alex and Riley by one each, which is consistent with
  one check per persona taking two judge answers.

**Alex, by segment** (the evaluation was interrupted; see incidents):

| Segment | Tasks fully passed | Checks passed |
|---|:---:|:---:|
| 001–048 (healthy disk) | 35 / 48 | 120 / 162 |
| 049–056 (graded while the disk was filling; validated, stand) | 4 / 8 | 13 / 26 |
| 057–200 (closing resume, 057 re-run fresh) | 89 / 144 | 349 / 531 |

**Repairs and re-runs (all logged per task):**
- **App-call repairs:**
  - Morgan: 101 calls on 89 tasks. Null rule 93, declared-default 6 (tasks 046, 114, 147,
    167), numeric-representation 2 (task 129).
  - Alex: 107 calls on 78 tasks. Null rule 96, declared-default 11 (10 tasks).
  - Riley: 38 calls on 30 tasks. Null rule 38.
  - The numeric-representation rule touched task 129 on Morgan and nothing else.
- **Guard-crash re-runs** (the exact-match guard, at most 2 per task): Morgan 0.5.0 had 1, on
  task 104. The re-run graded normally. Alex and Riley had 0.
- **Infrastructure re-runs** (operator ruling, closing card): 2 in total. Alex task 057's
  cut-off attempt and Riley task 001's cut-off attempt were each quarantined and re-run once.

## Costs (cash, against the USD 50 cap)

### Per leg, per run directory

| Leg | Morgan a1 (0.4.0, superseded) | Morgan (result) | Alex | Riley |
|---|:---:|:---:|:---:|:---:|
| Embeddings, text-embedding-3-large (ingestion) | $0.066517 (511,669 tok / 34 req) | $0.066517 (511,669 / 34) | $0.066728 (513,292 / 51) | $0.067462 (518,937 / 51) |
| Agent, Luna via relay | $0.610491 (887 calls) | $1.067016 (1,373 calls) | $1.056074 (1,489 billed calls) | $1.442290 (1,404 billed calls) |
| Judge, Sol via relay | $0.516020 (114 calls) | $0.901562 (178 calls) | $0.981390 (189 calls) | $1.903799 (214 calls) |
| **Total** | **$1.193028** | **$2.035095** | **$2.104192** | **$3.413550** |

- **Whole run: USD 8.745864** (unrounded sum 8.74586426; the rows are each rounded on their
  own). That is 17.5% of the USD 50 cap. The run never came near a cap stop.
- **Checkpoint projection after Morgan: USD 7.36.** Actual: USD 8.75. Alex and Riley cost
  more per task than Morgan's rates predicted. Riley's judge leg alone was USD 1.90.
- **Alex, before and after the disk-full stop:**
  - before (56 graded): USD 0.687583 (agent 0.333764, judge 0.287091, embeddings 0.066728);
  - closing resume: USD 1.416609 (agent 0.722310, judge 0.694299).
- **Riley:** the failed first evaluation billed USD 0 for the agent and the judge.

### How each figure was reconstructed, and how confident it is

Method: tools in the reporting card's workspace, read-only against the run root, aggregate
numbers only.

- **Agent leg.** This is the OpenRouter-billed `cost_usd` on each agent-relay `end` record.
  It was summed two ways, and both give the same total for every run directory:
  1. from the per-tag relay logs (each line fsynced);
  2. from the main relay log, skipping unparseable lines.
  Calls were paired start → end by call id. Every end appears in both sources, with no cost
  disagreements. The benchmark runner's own `out/costs/tests.json` reproduces the agent leg
  exactly for Morgan, Alex and Riley.
- **Judge leg.** This is the judge relay's per-call `cost_usd`. Every call ties one-to-one to
  a judge answer recorded in a standing grade file (counts above).
- **Embeddings leg.** OpenAI-reported ingestion token counts × list price
  (USD 0.13 / 1M tokens), from the run's ingestion accounting. It is computed, not a billing
  record. `out/costs/ingestion.json` agrees.
- **Account-side cross-check.** OpenRouter's account activity for 2026-11-24 (UTC) was
  compared with every relay record of that day: this run, plus the morning's smoke re-runs
  (run2, run3, zo-smoke-morgan) and the closing card's 2 health calls.
  - Sol on Azure: USD 2.841856 over 556 requests. This matches the relay records exactly, to
    the micro-dollar and to the request.
  - Luna on Azure: USD 3.133973 over 4,305 requests. Relay records account for all but
    **USD 0.000830 and 5 requests**.
  - The 2026-11-25 activity was not yet available (HTTP 400). Riley's post-midnight part
    (agent USD 1.387415, judge USD 1.808434) therefore has no account-side cross-check. Its
    records parse cleanly and its `costs.json` agrees.

Per persona:
- **Morgan (result) and Morgan a1: high confidence.** The records are complete: 0 malformed
  lines, 0 open calls, 0 uncosted ends. `morgan/costs.json` matches. Morgan a1 never wrote
  a `costs.json` (it stopped at task 129), so its figure is the relay and accounting sum.
- **Alex: high confidence. `alex/costs.json` is empty (0 bytes) and cannot be parsed.**
  - Why it is empty: the run's strict `costs.py` crashed on the 3 ENOSPC-truncated lines of
    the main agent-relay log, so the file was written empty.
  - The 3 truncated lines are `start` fragments. No billed `end` is lost: every end exists in
    the fsynced per-tag logs.
  - 54 agent calls (tasks 049–057, 17:27:58–17:42:52Z) have a `start` and no `end`. All 54
    `start`s are in the main log and none are in the per-tag log. In the relay's code
    (`agent_relay.py` `do_POST`), the `start` is logged to both files before the request is
    forwarded, outside the forwarding `try`. A failed per-tag write therefore aborts the call
    before it goes upstream. Those 54 calls were refused locally and never billed.
  - The 5 resume-time ends with no cost (tasks 057, 058, 060, 21:26–21:30Z, just after the
    Azure route came back): OpenRouter's `/generation` now answers 404 for all 5 ids, so
    none was billed.
  - Bounds: from the records alone, any unrecorded agent spend for Alex is at most 54 × the
    largest single call = USD 0.250650. The account-side check narrows this to
    **≤ USD 0.000830** for the whole day. **Neither bound is added to the total.**
- **Riley: high confidence.** `riley/costs.json` matches (USD 3.413551 there; it rounds each
  leg before adding). The 27 uncosted HTTP 200 ends and 9 HTTP 502 ends all belong to the
  outage attempt of task 001. `/generation` answers 404 for all 27 ids (re-checked by this
  card), so none was billed.

**Bounded residual not in any ledger: query-time embeddings.**
- **What it is.** Each `zo_recall` embeds its query with `text-embedding-3-large` on the
  OpenAI key (no HyDE, no reranker). Neither the harness nor the run's cost files record
  this.
- **Counts.** The persona stores' audit tables record the vector searches (read from scratch
  copies): Morgan a1 199, Morgan 375, Alex 366, Riley 624, so 1,564 across all attempts.
- **Bound.** Each query is at most 169–222 bytes (largest per run dir, from the traces).
  Tokens ≤ bytes, at USD 0.13 / 1M, so the leg is **≤ USD 0.041** in total (Morgan a1
  ≤ 0.0044, Morgan ≤ 0.0095, Alex ≤ 0.0094, Riley ≤ 0.0180). It is stated as a bound and
  not allocated. With it, the run is still under USD 8.79.

### Wall-clock per persona (UTC, from stage logs)

| Persona | Window | Stage time | Evaluate |
|---|---|---|---|
| Morgan a1 (0.4.0, superseded) | 11-24 11:09:08–13:07:53 | 7,099 s (1 h 58 m) | 128 graded, then 3 aborts on task 129 |
| Morgan (result) | 11-24 13:16:24–16:27:46 | 11,452 s (3 h 11 m) | 11,215 s, 56.1 s/task (incl. the task 104 re-run) |
| Alex | 11-24 16:29:52–23:49:23 | ≈ 13,280 s (3 h 41 m) | ≈ 4,318 s for 001–056, then the ENOSPC death (~17:46–17:47Z); stopped 3 h 38 m; resume 8,660 s for 057–200 (60.1 s/task) |
| Riley | 11-24 20:02:21 – 11-25 03:14:48 | 15,465 s (4 h 18 m) | 2,848 s outage attempt (0 graded); stopped 2 h 54 m; resume 12,295 s for 001–200 (61.5 s/task) |

Prepare + ingest + freeze took 4–5.5 minutes per persona. Adapter ingestion itself took
67 s (Morgan), 109 s (Alex) and 120 s (Riley). The v2 freeze was verified by a fresh locked
server process.

## Incident account

In time order. Times are UTC, 2026-11-24 unless marked otherwise. Sources: the run root's
`full-status.txt` and `orchestrator.log`, each run directory's stage logs and relay logs, and
the cards' PROGRESS records.

1. **Morgan 0.4.0: systematic guard abort on task 129 (13:04–13:08Z).**
   - Under adapter 0.4.0, task 129 tripped the benchmark's exact-match guard ("app call has
     no matching conversation tool call") on its first attempt and on both fresh re-runs.
     That reached the policy bound, so Morgan's evaluate stopped (rc 4) at 128/200 graded.
   - Diagnosis (kinds of difference only): one numeric argument was an int in the transcript
     and a float in the app log. The release's server coerces to the declared float type
     before it logs.
2. **Mid-run repair: adapter 0.5.0 (13:16Z).**
   - zo_harness.py 0.5.0 adds one disclosed rule, "numeric-representation". It runs only
     after the exact, null and declared-default rules fail. It replaces an app-log number
     with the transcript's number at the same key path when the two are numerically equal and
     differ only in int/float type (bools excluded). The post-repair match must still be
     exact.
   - Offline check against the benchmark's own `grading_calls` on 180 saved evidence files:
     the 173 accepted files were unchanged, and the 7 crashed attempts passed.
   - Morgan restarted from a fresh run directory (fresh ingest, freeze and all 200 tasks).
     The 0.4.0 attempt is preserved as `morgan-a1`. It is not merged into any result, and its
     USD 1.193028 counts against the cap.
   - The rule touched **task 129 only** (2 calls) across the whole run.
   - Under 0.5.0 one further guard crash occurred, on task 104. Its fresh re-run graded
     normally (not systematic).
3. **Alex: root disk full, first evaluation dies (17:28–17:47Z).**
   - From ~17:28Z (task 049) the VPS root filesystem was nearly full. The agent relay's
     fsynced per-tag writes began to fail. The 54 agent calls refused locally (above) fell on
     tasks 049–057, and the agent's client retried them.
   - After task 057's attempt, the Runner's state write failed with
     `OSError: [Errno 28] No space left on device`. The evaluate unit died without writing
     its exit file (rc 98, recorded 17:47:06Z), and the orchestrator stopped by its own rule.
   - The same ENOSPC truncated 3 lines of the main agent-relay log. That made the strict
     in-run cap check crash from ~17:31Z (`orchestrator.log` tracebacks), and later left
     Alex's `costs.json` empty.
   - Alex then stood at 56/200 graded.
   - **The operator's remediation:** backups were cleared from the root disk, and the
     benchmark data was moved to a Hetzner volume behind the same path. This is from the
     operator's own record. What the VPS shows: 29 GB root free by 19:54Z, and the run root
     now served from the data volume (/dev/sdb) behind
     `/opt/zouroboros/benchmark-data/dolphinbench`.
   - The original card's notes and the continuation card did not identify the process that
     filled the disk.
4. **The original card's 6-hour timeout.**
   - The original card (t_8f00fc5b) was shipped at 10:54:51Z. Its session was ended by its
     6-hour limit at ~16:55Z (the session log ends in the signal handler's
     KeyboardInterrupt).
   - That was during Alex's evaluation. The detached orchestrator carried on without a
     supervising card until the ENOSPC death above.
5. **The continuation card's stop (19:53–21:08Z).**
   - The continuation card (t_b68d5563) found the run not live. Resuming Alex needed a
     re-run on a non-guard crash, which its brief did not allow and which it could not get
     ruled on (no operator reachable). It left Alex as the orchestrator had left it and
     started Riley alone (20:02Z).
   - Riley's first orchestrator launch did not start: a relative script path in a unit with
     no working directory. The relaunch was otherwise identical.
   - After Riley's outage stop (item 6), the card wrote a script for a fresh Riley restart.
     The operator stopped the re-shipped worker (operator record). On the VPS, its session
     ends at 21:08:37Z on an interrupted command (exit 130). The restart script was never executed: no `riley-a1`
     directory exists and no RESTART line is in `full-status.txt`. Riley's preserved
     ingest/freeze and its first attempt were left for the closing card.
6. **Riley: pinned-provider outage, rc 1 (20:09–20:55Z).**
   - From Riley's first task call, every agent call came back one of two ways:
     - HTTP 200 after ~42 s with an empty, unbilled stream (27 calls);
     - HTTP 502 "Provider returned error" after the relay's 5 upstream retries (9 calls).
   - Task 001 used the benchmark's own transient-retry budget: 4 attempts, 528–1,164 s
     each. The Runner then raised "no complete recorded response", and evaluate exited rc 1
     at 20:55:41Z with 0/200 graded.
   - OpenRouter's endpoint list showed the **Azure** endpoint for `openai/gpt-5.6-luna` (the
     run's pinned route, fallbacks off) at status −5 and 0% recent uptime. The OpenAI and
     Bedrock endpoints were at 100%. Credentialed minimal calls pinned to Azure returned
     HTTP 502 at 21:09, 21:17 and 21:19Z.
   - **Ruled environmental:** no defect in adapter 0.5.0 or the harness, and no version
     change.
   - The cut-off attempt was quarantined (`riley/quarantine/001-resume-attempt1`). Task 001
     then re-ran, and Riley graded clean (0 guard crashes).
7. **The validation ruling and its outcome (closing card t_b6af091e, from 20:57Z).**
   - Marlando's ruling: validate Alex's 56 preserved grade files. Files that pass stand;
     files that fail are quarantined and re-run.
   - The validator applies the benchmark's own per-row submission checks:
     - strict parse, exact field sets, settings, and the request matching the published test;
     - check counts and indices;
     - judge message checks and the judge identity;
     - an **offline re-grade** that replays each grade's own recorded judge answers (no
       provider call). It must reproduce every verdict.
   - One disclosed tolerance: the three fields OpenRouter adds to judge assistant messages
     (`reasoning`, `refusal`, `reasoning_details`).
   - Calibration on Morgan's banked grades: 200/200 PASS (457/591, the banked result).
   - **Outcome: 56/56 Alex files PASS. 0 quarantined, 0 re-run.** The 8 disk-window tasks
     049–056 stand and are flagged above.
   - Task 057 had no grade file. Its cut-off attempt (an interaction marker, no evidence) was
     quarantined and re-run fresh.
   - After Alex completed, the same validator passed all 200 Alex grade files.
   - The validator was not run on Riley's grades. Under the ruling they stand as graded, all
     written after the outage had cleared.
8. **Closing resume (21:19Z – 11-25 03:14Z).**
   - A detached driver waited for a real pinned-Azure call to succeed: the first health call
     failed at 21:19:45Z and the second succeeded at 21:24:45Z.
   - It then resumed Alex from 56/200 (21:24:47Z, prepare/ingest/freeze skipped as done) to
     200/200 at 23:49:34Z: 0 guard crashes, 0 transport stops.
   - It then resumed Riley from 0/200 (23:49:37Z, ingest/freeze preserved) to 200/200 at
     11-25 03:14:49Z.
   - Disk watches on the root disk and the run volume (stop at < 3 GiB free) never fired.
     The lowest free space they saw was 28.5 GiB on root and 47.9 GiB on the volume.
   - One tooling change was made and disclosed: ead1c18, which makes `full_cost.py` skip
     unparseable JSONL lines so the cap check no longer crashes on Alex's truncated log.
     `runner/` (incl. zo_harness.py, the run identity), `full_run.sh`, `stage.sh`,
     `launch.sh` and `quarantine_task.py` are byte-identical to 094bed4.
9. **The closing card's own timeout.**
   - The closing card was shipped at 20:57:45Z. Its session was ended by its 6-hour limit at
     ~11-25 02:58Z, during Riley's resume, again in the signal handler.
   - Its detached driver finished Riley on its own at 03:14:49Z.
   - The closing card never ran the post-run credential scan. That scan and this report were
     done by the reporting card.

## Credential hygiene and post-run log scan

The closing card died before it ran the remediated procedure's post-run scan. The reporting
card ran it on 2026-11-25, ~04:18–05:01Z.

**Procedure.** `scripts/scan_logs.py` ran as detached `systemd --user` units:
- one unit per run directory (morgan-a1, morgan, alex, riley), each checked against its own
  issued-relay-token ledger;
- one unit for the run root's top-level files plus the closing card's evidence and log.

The Hermes source checkout (`hermes-source`, not run output) was excluded, as the procedure
says. The scan prints counts and paths, never matched text.

**Scope:** 270,318 files, 37.65 GB.

**Result:**
- **Exact secret values** (the run's OpenAI key, OpenRouter key and judge relay password):
  **0 hits.**
- **Issued relay tokens** (131 + 201 + 201 + 201 per-interaction tokens, checked by hash):
  **0 hits.** The `relay-tokens` directories are empty, so every token was revoked.
- **Credential-shaped strings:** every hit was classified by path, and every hit is a false
  positive.
  - **Vendored files.** Most hits are in the Hermes `bin/tirith` binary and the bundled
    `hermes-agent` skill docs. The same files exist in every test profile (including the
    quarantined ones), and they are the known vendored examples.
  - **Opaque blobs.** 36 `sk-` shape hits are in 36 test profiles' `state.db` (plus one
    Morgan-a1 grade file). Each one is the substring "sk-" in the middle of a 1,256–5,943-char
    opaque base64 run. Most sit under a model `encrypted_content` field. None appears in the
    published release, and none has a key's length or structure.
  - **Dataset content.** All of Alex task 128's hits are one 27-character record id (JSON
    keys `id` / `entry_id`). The identical string is in 14 files of the published benchmark
    release, so it is dataset content.
- **Verdict: no credential material in the run's logs or outputs.**

**After the scan.** As the procedure requires, the run's env-files (zo.env, relay.env,
judge.env) were removed from tmpfs and their directory was removed. No dolphinbench unit
was running at the time.

## Not done here

- No leaderboard or hosted-validation submission was made.
- The README is not changed: publication is a separate operator decision.
- No figure in this report was re-run, re-graded or adjusted. Figures that the records could
  not tie are stated as bounds and are not included in the totals.
