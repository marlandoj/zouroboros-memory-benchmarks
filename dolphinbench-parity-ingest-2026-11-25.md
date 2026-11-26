# DolphinBench — Zouroboros memory, production-parity ingest arm (2026-11-25)

Commissioned by Marlando, 2026-11-25. Built and launched by card t_62ebcf2b, adopted by
t_9e06acdd, and resumed, completed and reported by t_5d208ef3. This is a **new arm**,
reported against the direct-ingest baseline (adapter 0.5.0, 428/600,
`dolphinbench-full-2026-11-24.md`). It is not a repair of that run.

**Aggregate results only:** no dataset rows, histories, dialogue, app state, task text or
judge text appear here.

## Outcome

| Persona | Tasks fully passed | Checks passed | Judge-called checks passed | Disposed (failed by ruling) |
|---|:---:|:---:|:---:|:---:|
| Morgan Chen | **158 / 200 (79.0%)** | **463 / 591 (78.3%)** | 149 / 180 | 0 |
| Alex | **118 / 200 (59.0%)** | **454 / 719 (63.1%)** | 120 / 185 | task 035 (0 / 3 checks) |
| Riley | in flight | in flight | in flight | — |
| Pooled so far (Morgan Chen, Alex) | **276 / 400 (69.0%)** | **917 / 1,310 (70.0%)** | | 1 task |

> **INTERIM REVISION.** This revision was written while Riley's evaluation was still running (card t_5d208ef3 reached its session limit first). Morgan and Alex are final. Riley's row, the pooled 600-task result, the field placement and Riley's recall replay and scan are filled in by the next revision of this file, from the same tools. Until then, nothing below is a pooled result.

- **Morgan: 158 / 200 (baseline 156).** This is the one persona where the parity arm scored above the direct-ingest baseline, on tasks and on checks (463 vs 457).
- **Alex: 118 / 200 (baseline 128), with task 035 counted as failed by operator ruling.**
  - Alex lost 10 tasks and 28 checks against the baseline.
  - On the 199 tasks both arms graded, 27 passed only in the baseline and 17 only in the arm.
  - The baseline did not fully pass 035 either, so the disposition does not account for the gap.
- **The arm adds no observed recall from the observations layer.** For both personas, 0 of the served recall items were beliefs. What changed what the agent saw is the extracted-fact layer: 24.7% of Morgan's served items and 15.9% of Alex's.
- **It cost more agent work.** Alex made 19% more `zo_recall` calls than the baseline. One Alex task (035) looped on recall to the 60-turn cap on two attempts.

**Alex task 035 is scored as FAILED by operator ruling. It is not an ordinarily graded task.**
- Its three bounded attempts all ended without a submittable transcript. Attempts 2 and 3 hit the agent's 60-turn cap in a recall loop (37 and 39 `zo_recall` calls).
- The operator ruled it failed, and no further attempt was authorised.
- It has no grade file and no graded checks. It counts in Alex's denominator (200 tasks) as a failed task, and its 3 checks count as not passed.
- Everywhere below it is flagged "disposed". See the incident account.

## What changed relative to the baseline (adapter 0.5.0 → 0.6.0)

These are unchanged from the baseline:
- the agent (Hermes reference build, GPT-5.6 Luna, reasoning high, max 60 turns);
- the plugin bytes (`zo_recall` only, so the agent never writes memory);
- the profile templates, toolsets and model settings;
- the judge (GPT-5.6-Sol, medium);
- the three disclosed app-call repair rules;
- the embedder (production `text-embedding-3-large`).

Benchmark and grading code (mem0ai/dolphinbench @ 81cb6f8) are untouched.

The ingest stage keeps the baseline's verbatim pass, which stores one fact, one episode and one embedding per history message. It then adds two stages before freeze. Both reuse the exported production functions unchanged (zouroboros-workspace PR #1117; runner side zouroboros-memory-benchmarks PR #7).

1. **Extraction.**
   - Each session's message is one chunk. It goes through the memory package's exported capture extraction, `capture.ts` `extractFromText`, which is the extractor behind `autoCapture`.
   - Extracted facts are stored through `storeFact` with autoCapture's write parameters and carry `layer: extracted`. `created_at` is rewound to the narrative date.
   - Extracted episodes go through `createEpisode` with `happenedAt` set to the narrative date.
2. **Consolidation.** `consolidateObservations` for the persona with the production defaults: `minProof` 2, `useLlm` false.
3. **Recall union.** `RECALL_MERGE_RULE` in adapter.ts is `{observationShare: 0.25, order: observations-first, dedup: drop-belief-if-newest-evidence-fact-on-page}`:
   1. Facts come from `searchFactsHybrid(query, 20)` over both fact layers. Its ranking and its 60-char overlap dedup are unchanged.
   2. Beliefs come from `searchObservations(query, persona)` as exported. It does a substring match on the belief text or entity, excludes faded beliefs, and orders by proof count, then recency.
   3. Beliefs take at most `floor(limit × 0.25)` = 5 of the plugin's 20 slots.
   4. A belief is dropped when its newest supporting fact is already on the page. Facts are never dropped for a belief.
   5. Beliefs come first, then facts. The page is cut to 20, so beliefs displace facts from the tail only.
   6. An extracted-fact excerpt is labelled `entity[.key]: value`. A verbatim excerpt is the message itself. The plugin is unchanged: dated excerpts, each capped at 1,500 characters.
4. **Freeze.** Checkpoint v3. Its content hash and counts also cover observations (every column) and evidence links. A fresh locked server process verified every checkpoint.

### Extractor: read this alongside every number

- **The extractor is heuristic.** The exported capture extractor matches sentence patterns and **makes no model call**. So the recorded extractor model is `null`, and the extraction leg costs only the embeddings of the extracted facts.
- **The model-backed extractor was not used.** That is `standalone/auto-capture.ts` `extractFacts`. It is a module-private function of a CLI script that runs `main()` on import, so it is not reusable as exported, and per the commission it was not forked.
- **What this arm measures.** It measures production's *exported* capture and Observations path. It does not measure an LLM extraction path.

## Results

### Per persona and pooled, against the direct-ingest baseline (0.5.0)

| Persona | Arm: tasks | Baseline 0.5.0: tasks | Δ tasks | Arm: checks | Baseline: checks | Δ checks |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Morgan Chen | 158 / 200 | 156 / 200 | +2 | 463 / 591 | 457 / 591 | +6 |
| Alex | 118 / 200 | 128 / 200 | -10 | 454 / 719 | 482 / 719 | -28 |
| Riley | in flight | 144 / 200 | | in flight | 462 / 610 | |
| Pooled so far (Morgan Chen, Alex) | 276 | 284 | -8 | 917 | 939 | -22 |

Common-task comparison with the baseline, over the tasks each arm graded. A task counts as passed when all of its checks pass.

| Persona | Common graded tasks | Both pass | Arm only | Baseline only | Identical check vectors |
|---|:---:|:---:|:---:|:---:|:---:|
| Morgan Chen | 200 | 147 | 11 | 9 | 180 |
| Alex | 199 | 101 | 17 | 27 | 155 |

Alex task 035 (disposed) was **not fully passed** either in the baseline.

### Against the published Hermes + Luna field (600 tasks, agent-mediated ingestion)

Placement needs the pooled 600-task result: Riley is in flight.

How to read this:
- **Ingestion differs from the published rows.** Both Zouroboros arms ingest the history directly through the adapter. The published rows used agent-mediated ingestion. The placement shows where the number falls; it is not a like-for-like rank.
- **Run-to-run variation is of the same order as the arm-vs-baseline differences.** Morgan's arm and baseline share 180 of 200 identical check vectors, and the tasks that flip go both ways (arm-only vs baseline-only, above).

### Per-kind split (the benchmark's grader types, per graded check)

| Check type | Morgan Chen | Alex | Pooled |
|---|:---:|:---:|:---:|
| field_equals | 282 / 362 | 310 / 475 | 592 / 837 |
| field_llm_judge | 149 / 187 | 120 / 200 | 269 / 387 |
| datetime_absolute_eq | 6 / 6 | 17 / 31 | 23 / 37 |
| field_list_includes | 5 / 7 | 4 / 6 | 9 / 13 |
| field_eq_number | 11 / 12 | — | 11 / 12 |
| field_regex | 3 / 5 | — | 3 / 5 |
| field_markdown_bullets | 1 / 4 | — | 1 / 4 |
| field_list_equals_unordered | 3 / 3 | 0 / 1 | 3 / 4 |
| tool_called | 1 / 1 | 3 / 3 | 4 / 4 |
| tool_success_count | 2 / 3 | — | 2 / 3 |
| field_equals_all_calls | 0 / 1 | — | 0 / 1 |

Alex's disposed task 035 is not in this table: it has no graded checks.

### Repairs and re-runs (all logged per task)

- **Morgan Chen:** app-call repairs: 103 calls on 86 graded tasks (null 92, declared-default 11). Quarantined attempts: 129-attempt1, 129-attempt2.
- **Alex:** app-call repairs: 103 calls on 75 graded tasks (null 87, declared-default 16). Quarantined attempts: 035-attempt1, 035-attempt2, 080-attempt1, 152-attempt1.
- The quarantined attempts are kept under `<persona>/quarantine/`. Each is preserved, never merged into a result, and its cost counts. The causes are in the incident account.

## Recall composition (what the agent was actually served)

`tools/recall_replay.ts` replayed every `zo_recall` query of each persona's test phase. It ran against a scratch copy of that persona's frozen store, through the same `recall()` the adapter serves. It counted the layer of every item on every page, and the scratch copies were deleted afterwards.

| Persona | zo_recall queries replayed | Pages | Items | Verbatim | Extracted | Observations | Pages with a belief |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Morgan Chen | 396 | 396 | 7,414 | 5,582 | 1,832 (24.7%) | **0** | 0 |
| Alex | 436 | 436 | 7,928 | 6,671 | 1,257 (15.9%) | **0** | 0 |
| Riley | pending | | | | | | |

The smoke (Morgan, first 25) replayed 25 pages and 451 items: 352 verbatim, 99 extracted and 0 observations.

**The observations layer contributed nothing at recall: 0 belief items on any page of any replayed persona.**
- **Why.** Production `searchObservations` matches the agent's *whole query* as a substring of a belief's text or entity. Natural-language recall queries almost never are substrings of a belief, so the beliefs are built, frozen and hashed, but never reach a page.
- **Consequence.** The arm's recall is in practice verbatim plus extracted facts.
- **A second production effect.** `searchFactsHybrid`'s 60-char overlap dedup drops a verbatim message from the page when an extracted fragment of it ranked higher. The agent then sees the shorter, labelled fragment instead of the message.

## Extraction and consolidation counts per persona

| Persona | History messages (verbatim) | Extraction: chunks / empty / failed | Extracted facts | Extracted episodes | Consolidation: created / refined / contested / faded | Groups below proof | Evidence links | Checkpoint v3: facts / episodes / observations |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Morgan Chen | 3,400 | 3,400 / 1,836 / 0 | 2,155 | 692 | 122 / 0 / 0 / 0 | 1,365 | 4,190 | 5,555 / 4,092 / 122 |
| Alex | 5,011 | 5,011 / 2,426 / 0 | 2,650 | 966 | 112 / 0 / 0 / 0 | 1,680 | 5,981 | 7,661 / 5,977 / 112 |
| Riley | 5,128 | 5,128 / 2,474 / 0 | 2,456 | 1,386 | 94 / 0 / 0 / 0 | 1,752 | 5,832 | 7,584 / 6,514 / 94 |

The extractor is `capture.ts#extractFromText` (heuristic patterns, model `null`). Consolidation ran with `minProof` 2 and `useLlm` false. No extraction chunk failed for any persona.

## Costs (cash, against the USD 75 arm cap)

| Leg | Smoke (Morgan, 25) | Morgan Chen | Alex | Riley |
|---|:---:|:---:|:---:|:---:|
| Ingest, verbatim leg: embeddings (tokens) | $0.066517 (511,669) | $0.066517 (511,669) | $0.066728 (513,292) | in flight |
| Ingest, **extraction leg**: embeddings (tokens) | $0.005737 (44,134) | $0.005737 (44,134) | $0.007280 (55,999) | in flight |
| Ingest, **extraction leg**: model | $0.00 | $0.00 | $0.00 | in flight |
| Ingest, **consolidation leg**: embeddings + model | $0.00 | $0.00 | $0.00 | in flight |
| Agent, Luna via relay (billed calls) | $0.090057 (156) | $1.024346 (1,430) | $1.464769 (1,708) | in flight |
| Judge, Sol via relay (calls) | $0.113968 (23) | $0.898618 (180) | $0.980412 (188) | in flight |
| **Total** | **$0.276279** | **$1.995218** | **$2.519189** | in flight |

- **Arm total so far: USD 4.790686** against the USD 75 cap (6.4%), predecessor spend included. The arm includes every quarantined, superseded and disposed attempt, because their relay records stay in the run dirs.
- The direct-ingest baseline cost USD 8.745864 in total, including its superseded Morgan attempt. Per result persona it was Morgan 2.035095, Alex 2.104192 and Riley 3.413550.

**Bounded residual not in any ledger: query-time recall embeddings.**
- Each `zo_recall` embeds its query with `text-embedding-3-large`. No cost file records this.
- From the traces, including quarantined attempts, with the whole argument object's bytes taken as a token upper bound at USD 0.13 / 1M:
  - Morgan Chen: 398 calls, ≤ 39,068 bytes, so ≤ USD 0.005079.
  - Alex: 498 calls, ≤ 47,206 bytes, so ≤ USD 0.006137.
- The reporting replays re-embed the same queries once more. Together that is **≤ USD 0.0224**. It is stated as a bound and not added to the total.

## Incident account (unsmoothed)

Times are UTC on 2026-11-25. Sources: the run root's `full-status.txt` and `orchestrator.log`, each run directory's stage logs and relay logs, the run's `dispositions.json` and `*-reruns.jsonl`, and the three cards' PROGRESS records.

1. **The build card's ending (t_62ebcf2b).** The dispatcher's outbox records it as status `failed`, exit_code 1, error_class `auth`, finished_at 14:14:29Z. That timestamp is *earlier* than the card's own work: its session log was last written at 16:24:27Z and ends in "Gateway disconnected; turn outcome is unknown" after an interrupted wait (exit 130). Neither the build (PRs #1117 and #7, the smoke gate) nor the detached run depended on the session, and both were unaffected. Card t_9e06acdd adopted the live run at 17:31Z without stopping or restarting anything.
2. **The 15:18Z launch fumble.** The first full-run launch (15:18:42Z) did not start. The fresh run directories had no `logs/`, so `full_run.sh` could not open `logs/launch.log` before `launch.sh` created it. It logged "morgan relays failed" and exited. Nothing ran and nothing was spent. `logs/` was created and the identical command relaunched at 15:19:16Z.
3. **Storage pressure, handled before it bit.**
   - Each 200-task persona leaves ~9.6 GB of Hermes test profiles, ~44 MB each of which is a byte-identical vendored `bin/tirith`.
   - The data volume is shared with factory workspaces. It had about 20 GB free and dropped 7 GB from outside the run between 17:10 and 17:20Z.
   - A sweeper unit hard-links that file across *finished* tasks only. File content, mode and owner are unchanged, so it is storage only.
   - A disk-watch unit halts the run below 3 GiB free. It never fired. Over 80 samples, the lowest free space it logged was 14.0 GiB, at 2026-11-26T00:26:57Z.
4. **Morgan task 129: two guard crashes, third attempt graded.**
   - Attempts 1 and 2 (17:26Z, 17:27Z) tripped the benchmark's exact-match guard. The policy quarantined each one and re-ran it fresh, and attempt 3 was graded at 17:29Z. Task 129's result is therefore from its 3rd attempt, and the cost of both crashed attempts is counted.
   - Cause (keys and types only): the model sent `max_price_usd: null` explicitly and omitted another optional key in the same quote-list call. Disclosed repair rule 1 then drops both nulls, so the repaired call no longer equals the transcript's.
   - This is a latent gap in rule 1 (since 0.2.0), not the numeric class. It was not changed mid-arm.
5. **Alex task 035, attempt 1 (19:29:53Z): guard crash.** The agent passed arguments to `list_docs`, which takes none, and the release server logs `{}`. No exact match is possible and no rule covers it (agent-side). The policy quarantined it automatically (`035-attempt1`).
6. **Alex task 035, attempt 2 (to 19:39:57Z), and the orchestrator's false stop message.**
   - The agent used its whole 60-turn budget (60 model calls, 37 `zo_recall`) and ended on a tool call with no result. The release's `check_messages` rejected the transcript ("transcript: tool calls without results"). That is a non-guard failure.
   - `full_run.sh` then logged **"alex guard crash but 0 ungraded tasks (); stopping"** (rc 3). The message is false: its guard test greps `tail -n 60 evaluate.log`, which still held attempt 1's guard traceback.
   - This is a finding about the driver. It was not fixed mid-arm.
   - Minor adapter-side ordering flaw, disclosed and not changed: the adapter's repair step runs `check_messages` before the Runner persists its `.returned` evidence, so no `.returned` exists for attempts 2 and 3. The Hermes attempt journal and trace hold the same evidence.
   - The operator was unreachable. Card t_9e06acdd ruled one bounded fresh re-run (attempt 2 quarantined as `035-attempt2`, the last re-run the per-task bound allows) and relaunched at 19:42Z.
7. **Alex task 035, attempt 3 (19:44–19:55:42Z): the same turn-cap loop.**
   - 60 model calls, 39 `zo_recall`, and again a final tool call without a result.
   - The orchestrator stopped correctly as non-guard (rc 1). With the bound reached, the run stayed stopped for a ruling, and card t_9e06acdd ended at 20:03Z.
   - Attempt 3 was left in place: the `.inflight` marker, profile and trace.
8. **The operator's ruling on 035 (Marlando, 2026-11-25), final.**
   - Task 035 is scored as a **failed** task: its bounded attempts are exhausted, and no further attempt is authorised.
   - The turn-cap retrieval loop under the parity recall configuration is a **finding of this arm**:
     - No task of any persona reached 60 model calls in the baseline (maxima 28 / 37 / 32), nor in parity Morgan (maximum 17).
     - The baseline's 035 made 26 `zo_recall` calls.
     - Across all 200 tasks, parity Alex made 436 `zo_recall` calls against the baseline's 366 (+19%), over 1,375 vs 1,296 model calls. Sixty tasks made more recall calls than in the baseline, and 37 made fewer. These final-trace counts include 035's attempt 3. Morgan: 396 vs 373 recalls.
     - 035 is the only Alex task whose final trace reached 60 model calls. The baseline Alex maximum was 37.
   - The baseline also did not fully pass 035.
9. **This resume (card t_5d208ef3, from 20:06Z).**
   - Ownership was checked first: t_9e06acdd had ended and no unit was running.
   - 035 was recorded in `alex/dispositions.json`:
     - the ruling, the three attempts with their evidence paths and counts, and its 3 spec checks;
     - 0 graded and 0 passed.
   - Every aggregate counts 035 as a failed task in Alex's denominator of 200, flagged "disposed". It is never a grade file, and no check of it was fabricated.
   - **The one harness change that resuming required** (commit 049265a, pushed to PR #7):
     - The release Runner refuses to pass an `.inflight` marker ("Uncertain interaction … reconcile before resuming"), and the evidence had to stay in place. A filtered release would have changed the run identity.
     - So `run_smoke.py` evaluate now reads `<run>/dispositions.json` and runs the Runner's own per-test loop (`_execute` / `_grade` / cost collection, unchanged), skipping exactly the disposed ids.
     - Each entry must carry an operator ruling. With no such file, the code path is the original `runner.evaluate()`, which is what Morgan and Riley ran.
     - `run_smoke.py` is not part of the run identity (only zo_harness.py's SHA is), and benchmark and grading code are untouched.
     - An offline fake-Runner test checked the call order and the skip.
   - A dated note went into `full-status.txt` at 20:09:07Z. The orchestrator, dedup and disk watch were relaunched identically, and Alex resumed at 036 at 20:11:17Z.
10. **Alex task 080, attempt 1 (20:53–20:58:46Z): output-length truncation, non-guard.**
    - One of the attempt's 7 model calls returned 65,536 output tokens, the output cap, while the others returned at most 585. The agent driver ended with "Response truncated due to output length limit", and the benchmark's recorder failed ("Submission recording failed: SubmissionError").
    - The attempt made **0** `zo_recall` calls, so it is model-side output degeneration, not memory.
    - Under the brief's per-task bound (quarantine plus at most 2 fresh re-runs) this card quarantined it (`080-attempt1`, USD 0.082175, counted) and relaunched at ~21:02Z. The fresh re-run graded.
11. **Alex task 152, attempt 1 (22:20:57Z): guard crash, same class as 035's attempt 1.** The agent passed an undeclared argument (`doc_id`) to `list_docs`. The policy quarantined it automatically, and the fresh re-run graded.
12. **Alex complete at 23:08:52Z:** 199 graded plus 035 disposed. Riley started at 23:08:53Z.
13. **Riley (from 23:08:53Z).** Prepare finished at 23:10:30Z, ingest at 23:17:21Z and freeze at 23:18:11Z, and evaluate was running at about 1 task/min. *INTERIM: Riley's evaluation was still in flight when this revision was written.* Any Riley incident is added in the next revision, together with the final numbers.
14. **This card's own limit.** Card t_5d208ef3's session (6-hour limit, shipped at 20:04Z) ends before Riley finishes. The run is detached and does not depend on the session:
    - the orchestrator, the dedup and disk-watch units, and a post-run chain unit;
    - the post-run chain runs Riley's recall replay, Riley's scan and the run-root scans when Riley completes.

    The card's PROGRESS.md holds the exact steps an adopting card needs to finish the report and delete the env files.

## Credential hygiene and post-run log scan

**Procedure.** `scripts/scan_logs.py` ran as detached `systemd --user` units. Each persona run dir was checked against its own issued-relay-token ledger. The run root's top-level files (status, orchestrator, dedup and disk-watch logs, earlier scan logs) were scanned once against each persona's ledger. The Hermes source checkout is not run output and was excluded, as the procedure says. The scan prints counts and paths, never matched text. The smoke was scanned by the build card: 9,199 files, 0 exact hits, 0 token hits.

- `morgan`: 74,181 files, 10.39 GB; 3 exact values and 202 issued tokens checked. **0 exact hits, 0 token hits.** Shape hits: {'aws_access_key_id': 1010, 'bearer_header': 404, 'github_token': 808, 'openai_or_openrouter_sk_key': 2025, 'pem_private_key': 808, 'slack_token': 202}.
- `alex`: 75,184 files, 10.71 GB; 3 exact values and 204 issued tokens checked. **0 exact hits, 0 token hits.** Shape hits: {'aws_access_key_id': 1020, 'bearer_header': 408, 'github_token': 817, 'openai_or_openrouter_sk_key': 2281, 'pem_private_key': 816, 'slack_token': 204}.
- `riley`: pending
- `root-morgan`: pending
- `root-alex`: pending
- `root-riley`: pending

**Triage of the shape hits** (tools/triage_shapes.py; it reports lengths, keys and release presence, never values):
- **Vendored files.** Most hits are in each test profile's vendored `bin/tirith` and the bundled `hermes-agent` skill docs.
- **Morgan.** 5 `sk-` shapes, in the `state.db` of 5 test profiles. Each is a substring in the middle of a 2,104–3,880-char opaque base64 run.
- **Alex, opaque blobs.** 20 test profiles' `state.db` have hits: 19 `sk-` shapes and 1 GitHub-token shape (task 035's profile). Each starts in the middle of a 1,636–4,092-char opaque token run, mostly under `encrypted_content`. None occurs in the published release.
- **Alex, dataset content.** All of task 128's hits are one 27-character dataset record id (JSON keys `id` / `entry_id` and quotes of it). Its identical bytes are in 14 files of the published benchmark release, which matches the baseline's finding for the same task.
- **Verdict for Morgan and Alex: no credential material.**

*INTERIM: the scans of Riley's run dir and of the run root's top-level files run when Riley completes. The env files stay in place until then, and are deleted after the last scan.*

## Not done here

- No leaderboard or hosted-validation submission. No README change.
- The 0.5.0 run root (`full-2026-11-24`) was read only and not modified.
- Benchmark and grading code were not modified. No grade was re-run, re-graded or adjusted. The one disposed task is reported as failed and flagged; it was not graded.
