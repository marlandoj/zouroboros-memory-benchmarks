# DolphinBench — Alex confirmation re-run under the repaired parity configuration (2026-11-26)

Resolution 4 of the 2026-11-26 parity resolutions (Marlando's ruling). Built, run and reported
by card t_f99b6fa3. One persona (Alex), one run. It answers one question: with the two repairs of
zouroboros-workspace PR #1121 in place, does the production-parity ingest arm recover toward or
past the direct-ingest baseline on Alex, or is the extraction layer itself the drag?

**Aggregate results only:** no dataset rows, histories, dialogue, app state, task text or judge
text appear here.

## Outcome

| Alex | Tasks fully passed | Checks passed | Judge-called checks passed |
|---|:---:|:---:|:---:|
| **This run** (parity ingest, searchObservations v2, verbatim-priority recall) | **125 / 200 (62.5%)** | **481 / 719 (66.9%)** | 128 / 190 |
| Direct-ingest baseline (adapter 0.5.0, 2026-11-24) | 128 / 200 (64.0%) | 482 / 719 (67.0%) | — |
| Parity arm, recall union (adapter 0.6.0, 2026-11-25) | 118 / 200 (59.0%) | 454 / 719 (63.1%) | 120 / 185 |

- **Against the direct-ingest baseline: −3 tasks, −1 check.** On the 200 tasks both graded: 107
  passed in both, 18 only in this run, 21 only in the baseline; 161 tasks have identical check
  vectors.
- **Against the parity union arm: +7 tasks, +27 checks.** On the 199 tasks both graded (the
  parity arm's 035 was disposed): 102 in both, 23 only in this run, 16 only in the parity arm;
  160 identical check vectors.
- **Task 035 was graded in this run, and failed: 0 / 3 checks.** Attempt 1 crashed the
  benchmark's exact-match guard and was quarantined by policy; the fresh re-run (attempt 2 of a
  fresh bound of 3) passed the guard and was graded normally. The direct-ingest baseline also
  scored 035 at 0 / 3. In the parity arm 035 was never graded (three attempts without a
  submittable transcript, failed by operator ruling, 0 / 3 in the aggregate). So 035 contributes
  0 tasks and 0 checks to all three rows, and no row needed a disposition.
- **Observations served live: 0.** The beliefs layer is present and frozen (112 beliefs) and is
  retrievable under searchObservations v2, but under the verbatim-priority rule no belief reached
  a page. 99.7% of served items were verbatim messages.

## Configuration under test

Verified from the code before any paid call (card PROGRESS.md records each check).

- **Memory code.** zouroboros-workspace PR #1121 (OPEN at the start; not merged by this card; nothing deployed), head
  `memory/observation-term-retrieval` @ `34e8f4ff462ed370cc7e18df9f1e5a137f197469`, cloned and built
  fresh (core, intelligence, rag, memory). Against the parity arm's `945a5016` (an ancestor): no
  change in core, intelligence, rag, `capture.ts`, `facts.ts` or episodes; `observations.ts` changes
  only search (no consolidation line); `adapter.ts` changes only recall. The adapter reports 0.6.1.
  The PR was merged by the PR manager at 20:31Z, during this run's evaluation (merge commit
  `2f3940e6`, after a main-merge into the branch). That merge adds only an unrelated package
  (`packages/workshop-lessons`): core, intelligence, rag and memory are byte-identical between
  `34e8f4ff` and `2f3940e6`, so the tested memory code is also main's at the merge. The run's
  checkout was not changed while it ran.
- **Ingest: identical to the parity arm, into a fresh store built by this run.** Verbatim layer
  (one fact + one episode per message), heuristic extraction (`capture.ts` `extractFromText`, no
  model), `consolidateObservations` with `minProof` 2, `useLlm` false. Every ingest count equals
  the parity arm's: 5,011 messages; 2,650 extracted facts + 966 episodes from 5,011 chunks (0
  failed, 2,426 empty); 112 beliefs, 5,981 evidence links. Checkpoint v3 counts are identical
  (facts 7,661, episodes 5,977, embeddings 7,661, observations 112, evidence 5,981); the content
  hash differs, as fresh embeddings and ids make it.
- **Recall, for the entire run.** `searchObservations` v2 (`OBSERVATION_SEARCH_VERSION` 2: the v1
  substring tier, then beliefs sharing ≥ 2 query terms ranked by IDF sum) and
  `ZO_DOLPHINBENCH_RECALL_MERGE=verbatim-priority` (`VERBATIM_PRIORITY_RULE`: `searchFactsHybrid`
  pool of 3 × 20; verbatim facts fill the page first in hybrid order; only unused slots go to
  beliefs, at most 5, then to extracted facts). Both settings were recorded in the run's
  PROGRESS.md before evaluation started.
- **Harness.** The persisted zo-harness at PR #7's `049265a` plus one commit, `d97e9bf`
  (zouroboros-memory-benchmarks PR #9, OPEN): adapter pin 0.6.0 → 0.6.1, and `run_smoke.py` sets the
  merge switch from `zo_harness.RECALL_MERGE_RULE_NAME` and refuses any adapter server whose
  `/stats.recallMergeRuleName` differs, on every server start (prepare, ingest, freeze,
  evaluate). The rule is in the run identity. Plugin, profile templates, toolsets, model
  settings, relays and the three disclosed app-call repair rules are unchanged.
- **Unchanged from both prior arms.** Agent (Hermes reference build at the release pin with the
  release's evaluation patch; GPT-5.6 Luna, reasoning high, max 60 turns) through the same agent
  relay; judge (GPT-5.6-Sol) through the same judge relay; embedder `text-embedding-3-large`;
  benchmark and grading code (mem0ai/dolphinbench @ 81cb6f8) untouched. The Hermes source tree
  is byte-identical to the parity arm's (tree `8ce58b1f`); the agent image was rebuilt from it
  with the same builder.

## Live recall composition

Counted from the `zo_recall` results the agent actually received (Hermes test traces), each
served item matched against a copy of the frozen store by its text (exact, or prefix for the
plugin's 1,500-char cut). The same counter run on the parity arm reproduces that arm's as-run
replay exactly (436 pages, 6,671 / 1,257 / 0), which validates it.

| Alex | `zo_recall` pages | Items | Verbatim | Extracted | Observations |
|---|:---:|:---:|:---:|:---:|:---:|
| This run (verbatim-priority, v2) | 375 | 7,500 | 7,478 (99.7%) | 22 (0.3%) | **0** |
| Parity arm (union, v1), as run | 436 | 7,928 | 6,671 (84.1%) | 1,257 (15.9%) | 0 |
| Direct-ingest baseline | 366 | — | all | — | — |

- No served item was ambiguous between layers and none was unmatched.
- The 375 pages are those of the graded attempts. The quarantined 035 attempt 1 made 16 more
  `zo_recall` calls (391 in all).
- An offline replay of the same 375 queries through the same `recall()` (fresh query embeddings,
  copy of the frozen store) gives the identical split, 7,478 / 22 / 0, with 0 pages carrying a
  belief.
- **Why the observations count is 0.** Under verbatim-priority, beliefs take only the slots
  verbatim facts leave. Every page was full (20 items), and 7,478 of 7,500 items were verbatim, so
  at least 353 of 375 pages left no slot at all. On the pages that did leave slots, extracted facts
  (which rank after beliefs) filled them: 22 items. So on those pages no belief candidate matched
  the query or survived the newest-evidence dedup. Card t_2793bcd8's offline replay predicted
  this for the rule (Alex parity queries: 8,706 / 14 / 0). Repair A (searchObservations v2)
  therefore had no live effect on Alex in this configuration: this run measures repair B, the
  restoration of the verbatim page.

## Costs (USD; card cap 15)

| Leg | Calls / tokens | Cash |
|---|---|---:|
| Ingest — verbatim embeddings | 513,292 tok | 0.066728 |
| Ingest — extraction embeddings (no model calls) | 55,999 tok | 0.007280 |
| Ingest — consolidation (no model, no embeddings) | — | 0.000000 |
| **Ingest total** | 81 embedding requests | **0.074008** |
| Evaluation — agent (relay-billed) | 1,556 calls | 1.179424 |
| Evaluation — judge | 198 calls | 1.023376 |
| **Evaluation total** | | **2.202800** |
| **Run total** (`costs.json`) | | **2.276808** |

- The agent total includes 035's quarantined attempt 1 (23 calls, 0.035450); 035 attempt 2 cost
  0.103063 (59 calls).
- Recall-time query embeddings are in no cost file: 391 `zo_recall` calls, 37,033 query bytes;
  bound ≤ USD 0.0048. The post-run replay cross-check made one embedding call per query (same bound).
- Projection before evaluation: USD 2.445 for the evaluation on the parity arm's measured Alex
  rates (x2 margin → ~USD 5.0), against the cap of 15.
- Comparators: the parity arm's Alex leg cost 2.519189 (agent 1.464769 over 1,708 calls, judge
  0.980412 over 188 calls, ingest 0.074008).

## Incident account (complete)

1. **Alex task 035, attempt 1 — exact-match guard crash, 20:39:22Z.** `full_run.sh`'s uniform
   policy quarantined it (`alex/quarantine/035-attempt1`, evidence, attempt journal, cost file,
   profile and trace moved together) and started a fresh re-run. Structural diagnosis
   (`guard_diag.py`, keys and types only): 5 app calls against 32 transcript calls; an app-logged
   `list_docs` call `{}` had no exact transcript match because the agent's matching call carried an
   argument `list_docs` does not declare (`title`, a string). Same class as the parity arm's 035
   attempt 1 and 152 attempt 1. Agent-side; no repair rule covers it, and none was added.
2. **Alex task 035, attempt 2 (fresh re-run 1 of at most 2)** passed the guard and was graded
   (0 / 3 checks). The bound was not exhausted, so the run did not stop.

No other quarantine, re-run or stop. No non-guard failure. No disk halt: the data volume (shared
with other workloads) stayed between 4,506 and 7,160 MiB free against a 3,072 MiB halt floor; a
storage-only sweeper hard-linked the byte-identical vendored `bin/` files of finished tasks'
test profiles (content, mode and owner unchanged; in-flight tasks untouched), as in the prior
arms. The Hermes source was placed on the root filesystem (storage only).

## Post-run credential scan

Procedure as in the prior arms: `scan_logs.py` over the whole persona directory (incl.
quarantine), then over the run root's top-level files, each checked against the run's 3 actual
secret values and the 201 issued per-interaction relay-token hashes; then the env files were
deleted.

- **Persona directory: 73,970 files, 10.51 GB (apparent). 0 exact-value hits, 0 issued-token hits.**
- **Run-root top-level files: 4 files. 0 hits of any kind.**
- Shape hits: 1,005 lines in the vendored `bin/tirith` and 603 in the bundled hermes-agent skill
  docs inside test profiles (vendored examples, as in every prior run), and 17 other files, all
  `sk-` shapes, triaged without printing values:
  - Task 128 (8 files): one 27-char record id whose identical bytes occur in 14 files of the
    published release. Dataset content, as in both prior arms.
  - 9 test profiles' `state.db` (tasks 034, 035 attempt 2, 039, 060, 062, 112, 115, 122, 197): each
    match starts mid-run inside a 600–3,890-char opaque token run, mostly under
    `encrypted_content`; none occurs in the release. False positives.
- The run's env files (tmpfs) were deleted after the last scan; no run unit remains.

## What this comparison does and does not establish

It establishes, for Alex and for one run of each configuration:

- With extraction and consolidation still in the store, keeping their output off the recall page
  (verbatim-priority) brings Alex from the union arm's 118 / 454 to 125 / 481, within 3 tasks and
  1 check of the direct-ingest 128 / 482. The loss measured in the parity arm tracks what the agent
  was served (16% extracted fragments displacing verbatim messages), not the presence of the
  extraction layer in the store.
- The searchObservations v2 repair did not reach the agent here: 0 beliefs were served, so this
  run says nothing about whether beliefs help or hurt answers.

It does not establish:

- **That the configurations differ in a stable way.** Each configuration was run once, on one
  persona. Against the direct baseline 39 tasks changed outcome in opposite directions (18 / 21)
  for a net of −3; against the union arm 39 changed (23 / 16) for +7. Run-to-run variance of the
  same configuration has not been measured, so neither the −3 nor the +7 is shown to exceed it.
- **Anything about Morgan or Riley.** Their union-arm results differed in direction from Alex's
  (Morgan scored above its baseline); this run did not re-run them.
- **Separate effects of repairs A and B.** A contributed 0 served items, so the result is B's.
- **That verbatim-priority is right for production.** It is an adapter-side benchmark merge rule;
  nothing was merged or deployed.
