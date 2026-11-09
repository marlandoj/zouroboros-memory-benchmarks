# Zouroboros Memory Benchmarks

Published benchmark results for the **Zouroboros Intelligence Plane** memory system.

## Results

| Benchmark | Score | Reader | Judge | Date |
|-----------|-------|--------|-------|------|
| LongMemEval (full S, real embeddings) | **85.4%** | gpt-6.1-sol | gpt-4o | 2026-11-08 |
| LongMemEval (full S, current-judge variant) | **83.4%** | gpt-6.1-sol | gpt-6.1-sol | 2026-11-08 |
| LoCoMo | **58.3%** (K=10, threshold 0.2, text-embedding-3-large) | gpt-6.1-sol | gpt-4o | 2026-11-09 |
| LoCoMo | **53.5%** (K=10, vector threshold 0.2) | gpt-6.1-sol | gpt-4o | 2026-11-09 |
| LoCoMo | **42.8%** (K=10) | gpt-6.1-sol | gpt-4o | 2026-11-08 |
| BEAM (100K) | **54.4%** (ability-aware chrono) | gpt-6.1-sol | gpt-4o | 2026-11-08 |
| LongMemEval (full S, real embeddings) | **81.5%** | gpt-5-mini | gpt-4o | 2026-10-15 |
| LongMemEval (oracle, perfect retrieval) | **84.0%** | gpt-5-mini | gpt-4o | 2026-10-15 |
| LoCoMo | **40.7%** (K=100) | gpt-5-mini | gpt-4o | 2026-10-16 |
| BEAM (100K) | **47.8%** (chrono) | gpt-5-mini | gpt-4o | 2026-10-16 |

## 2026-11-09 LoCoMo — embedding model upgrade (58.3%)

The only change in this run is the embedding model: **text-embedding-3-small (1536d) → text-embedding-3-large (3072d)**. Reader, judge, threshold (0.2), and K are unchanged from the 53.5% run below.

This result reverses an earlier measurement, and the reversal is the interesting part. Under the old 0.46 gate, a paired probe of the two embedders was a coin toss (recall 63.2% vs 63.4%) — the gate discarded so much evidence before ranking that embedder quality was invisible. With the gate at 0.2, ranking decides, and a paired re-probe at 0.2 showed 3-large ahead +4.6pp on recall@10 over a 495-question subset (recall@30 was level — the larger model *ranks* better; it does not find evidence the small one misses entirely). The full-set run below confirms the subset signal.

1,986 questions, 0 errors, paired against the 53.5% run question-by-question.

| Category | n | 3-large | 3-small (t=0.2) | Δ |
|----------|---|---------|-----------------|---|
| open-domain | 841 | 80.9% | 73.7% | +7.1 |
| adversarial | 446 | 18.6% | 22.9% | −4.3 |
| single-hop | 282 | 51.4% | 41.5% | +9.9 |
| temporal | 96 | 51.0% | 49.0% | +2.1 |
| multi-hop | 321 | 62.3% | 54.8% | +7.5 |
| **overall** | 1986 | **58.3%** | 53.5% | **+4.8** |

**Evidence recall@K:** 91.3%, up from 87.7% — paired flips **+113 gained / 41 lost**. Accuracy flips +190 / −95, a net +95 questions answered correctly.

**The disclosed cost:** adversarial accuracy fell a further 4.3pp — the same mechanism as the threshold fix, one level deeper. Better retrieval surfaces more of the planted false presuppositions (23 adversarial questions flipped from recall-miss to recall-hit) and the reader still follows them. Adversarial now stands at 18.6%, against 39.0% in the 0.46 era: the cumulative price of actually retrieving what the conversations say, reported here rather than averaged away.

**Adoption:** text-embedding-3-large at its native 3072 dimensions is now the production embedder (zouroboros-workspace PR #1096, merged 2026-11-09), shipped together with a re-embedding migration for existing stores — stored vectors are dimension-filtered, so a model switch without a backfill would blind the vector leg. Embedding unit cost rises 6.5× ($0.02 → $0.13 per 1M tokens); at benchmark scale that is ~$0.02 of this run.
**Cost:** ~$5.08 (reader $4.50, judge $0.56, embeddings ~$0.02)

## 2026-11-09 LoCoMo — vector threshold fix (53.5%)

The 2026-11-08 run below diagnosed LoCoMo as "retrieval-ranking-bound." A miss autopsy on 2026-11-09 showed that diagnosis was wrong about the mechanism: extraction was complete and the fusion ranking was innocent — **96% of missed evidence existed in the store but was discarded by the vector leg's 0.46 similarity gate before ranking ever saw it** (median best-cosine of the discarded evidence: 0.415). The only change in this run is that gate: vector similarity threshold 0.46 → 0.2, the same value the LongMemEval runs already used. Reader, judge, embeddings, and K are unchanged.

1,986 questions, 0 errors. Reader gpt-6.1-sol, judge gpt-4o, K=10.

| Category | n | 2026-11-09 (t=0.2) | 2026-11-08 (t=0.46) | Δ |
|----------|---|--------------------|---------------------|---|
| open-domain | 841 | 73.7% | 55.2% | +18.5 |
| adversarial | 446 | 22.9% | 39.0% | −16.1 |
| single-hop | 282 | 41.5% | 28.7% | +12.8 |
| temporal | 96 | 49.0% | 31.3% | +17.7 |
| multi-hop | 321 | 54.8% | 31.5% | +23.4 |
| **overall** | 1986 | **53.5%** | 42.8% | **+10.7** |

**Evidence recall@K:** 87.7%, up from 61.1% — paired per-question flips **+527 gained / 0 lost**: lowering the gate displaced not one previously-retrieved evidence set. Net +212 questions answered correctly.

**The disclosed cost:** adversarial accuracy fell 16.1pp. LoCoMo's adversarial questions plant false presuppositions in the conversations; at the old threshold the planted sessions usually never reached the reader, and at 0.2 they do — 67 of the 89 adversarial losses are questions where retrieval newly surfaced the planted session and the reader followed it. This is a reader-robustness problem exposed by better recall, not a retrieval defect, and it is reported here rather than averaged away. Average reader context grew from 1,252 to 2,744 chars per question.

**Adoption:** 0.2 is now the production default (`DEFAULT_VECTOR_SIMILARITY_THRESHOLD`), adopted on this evidence under pre-registered bars (full-set recall ≥ 66%, accuracy ≥ 44% — both passed by wide margins).
**Cost:** ~$5.11 (reader $4.55, judge $0.56, embeddings ~$0.01)

## 2026-11-08 Re-run — current reader (gpt-6.1-sol)

Same system, same retrieval, same harness configuration as the October runs — the only change is the reader generation (gpt-5-mini → gpt-6.1-sol), selected by a measured shootout rather than by name. Primary judge stays gpt-4o (the official LongMemEval judge, and still the judge used by current published leaderboards) so the new numbers are directly comparable to the October numbers.

**Reader shootout** (100-question stratified LongMemEval probe, gpt-4o judge; control = the published gpt-5-mini configuration on the same 100 questions):

| Reader | Probe score | vs control |
|--------|-------------|------------|
| gpt-6.1-sol | **88.0%** | +4.0pp |
| gpt-5-mini (control) | 84.0% | — |
| gpt-5.6-sol | 84.0% | ±0.0pp |
| gpt-5.6-luna | 80.0% | −4.0pp |

### LongMemEval Detail (85.4% run)

500 questions, 0 errors. Real OpenAI embeddings. K=10, vector threshold 0.2, baseline path — identical to the 81.5% run.

| Category | n | 2026-11-08 | 2026-10-15 | Δ |
|----------|---|------------|------------|---|
| Knowledge update | 78 | 92.3% | 87.2% | +5.1 |
| Multi-session | 133 | 73.7% | 74.4% | −0.7 |
| Single-session assistant | 56 | 100.0% | 100.0% | ±0.0 |
| Single-session preference | 30 | 96.7% | 53.3% | **+43.4** |
| Single-session user | 70 | 97.1% | 95.7% | +1.4 |
| Temporal reasoning | 133 | 78.2% | 76.5% | +1.7 |
| Abstention | 30 | 73.3% | 80.0% | −6.7 |

**Retrieval:** Session recall@K 98.9%, evidence-turn recall@K 93.6% — identical to the October run, so the +3.9pp overall is attributable to the reader alone.
**Dual judge:** the same 500 answers scored 83.4% under a gpt-6.1-sol judge (judges agree on 97.2% of questions) — the current-generation judge is ~2pp stricter than gpt-4o on identical output.
**Cost:** $5.28 (embeddings $1.07, reader $3.76, gpt-4o judge $0.24, gpt-6.1-sol judge $0.21)

### LoCoMo Detail (42.8% run)

1,986 questions, 0 errors. Reader gpt-6.1-sol, judge gpt-4o. K=10.

| Category | n | 2026-11-08 | 2026-10-16 (K=10) | Δ |
|----------|---|------------|-------------------|---|
| open-domain | 841 | 55.2% | 55.8% | −0.6 |
| adversarial | 446 | 39.0% | 30.3% | +8.7 |
| single-hop | 282 | 28.7% | 30.1% | −1.4 |
| temporal | 96 | 31.3% | 28.1% | +3.2 |
| multi-hop | 321 | 31.5% | 27.7% | +3.8 |

**Evidence recall@K:** 61.1% — unchanged from October (61.0%). The stronger reader bought only +2.3pp overall because ~39% of the evidence still never reaches it. LoCoMo remains **retrieval-ranking-bound**, exactly as diagnosed in October; the new run also beats the old K=100 headline (40.7%) while using K=10.
**Cost:** $3.80 (embeddings $0.74, reader $2.50, judge $0.55)

### BEAM Detail (54.4% run, 100K tier)

400 questions (20 chats x 20), 0 errors. Nugget-rubric scoring via gpt-4o. Ability-aware chronological context (the configuration that scored 47.0% in October).

| Ability | n | 2026-11-08 | 2026-10-16 (ability-aware) | Δ |
|---------|---|------------|----------------------------|---|
| preference_following | 40 | 92.5% | 76.3% | +16.2 |
| instruction_following | 40 | 63.7% | 51.2% | +12.5 |
| knowledge_update | 40 | 62.5% | 60.0% | +2.5 |
| temporal_reasoning | 40 | 62.5% | 61.3% | +1.2 |
| information_extraction | 40 | 55.3% | 57.2% | −1.9 |
| abstention | 40 | 52.5% | 45.0% | +7.5 |
| multi_session_reasoning | 40 | 50.3% | 34.3% | +16.0 |
| contradiction_resolution | 40 | 48.1% | 53.8% | −5.7 |
| event_ordering | 40 | 29.4% | 11.1% | +18.3 |
| summarization | 40 | 27.4% | 20.1% | +7.3 |

Per-ability deltas inside the ±3–7pp run-to-run variance band documented below (information_extraction, contradiction_resolution) should not be over-interpreted. Summarization remains the structural weakness.
**Cost:** $7.67 (embeddings $1.03, reader $5.65, judge $0.99)

### Re-run findings

- A reader generation is worth **+3.9pp (LongMemEval), +2.3pp (LoCoMo), +7.4pp (BEAM)** on identical retrieval — but the three benchmarks bottleneck in different places, and only two of them pay the reader dividend in full.
- The LongMemEval preference weakness was a **reader** limitation (53.3% → 96.7%); multi-session aggregation did not move (74.4% → 73.7%) and remains a structural ceiling.
- LoCoMo is **retrieval-bound**: evidence recall@K is flat at ~61% across reader generations.
- The stronger reader abstains less on LongMemEval (80.0% → 73.3%) — it answers questions the weaker reader correctly declined.
- Total re-run programme cost (shootout + three full runs + smokes): **~$20.00**.

## LongMemEval Detail (81.5% run)

500 questions, 0 errors. Real OpenAI embeddings. K=10, vector threshold 0.2.

| Category | Accuracy |
|----------|----------|
| Single-session assistant | 100.0% |
| Single-session user | 95.7% |
| Knowledge update | 87.2% |
| Temporal reasoning | 76.5% |
| Multi-session | 74.4% |
| Preference | 53.3% |
| Abstention | 80.0% |

**Retrieval:** Session recall@K 98.9%, evidence-turn recall@K 93.6%
**Cost:** $2.19 (embeddings $1.07, reader $0.85, judge $0.28)

## Methodology

- **System:** Zouroboros Intelligence Plane — actor-scoped memory, three-signal retrieval (keyword + vector + graph), promotion pipeline, entity graph
- **Reader/Judge:** gpt-5-mini / gpt-4o (official LongMemEval judge prompts)
- **Embeddings:** OpenAI `text-embedding-3-small`
- **Reproduction:** harness in `zouroboros-workspace` (`packages/memory/src/longmemeval/`)
- **2026-11 re-run:** reader gpt-6.1-sol / judge gpt-4o (dual-judged with gpt-6.1-sol on LongMemEval); harness in the Zouroboros monorepo, branch `bench/longmemeval-adapter`, commit `a1b453f4` (adds GPT-6-class request handling and current-model pricing). Retrieval, embeddings, K and thresholds unchanged from October.

## License

Results published under CC BY 4.0. Benchmark datasets retain their original licenses.

## LoCoMo Detail (40.5% run)

1,986 questions, 0 errors. Reader gpt-5-mini, judge gpt-4o. K=10.

| Category | n | Accuracy |
|----------|---|----------|
| open-domain | 841 | 55.8% |
| adversarial | 446 | 30.3% |
| single-hop | 282 | 30.1% |
| temporal | 96 | 28.1% |
| multi-hop | 321 | 27.7% |

**Evidence recall@K:** 62.0% at K=100 (was 61.0% at K=10) — widening K barely moved the needle (+0.2pp overall). The problem isn't retrieval breadth, it's retrieval quality. Published baselines (Mem0 92.5%, Zep 94.7%) likely benefit from better ranking, not just wider K.
**Cost:** $3.06

## BEAM Detail (45.9% run, 100K tier)

400 questions (20 chats x 20), 0 errors. Nugget-rubric scoring via gpt-4o.

| Ability | Accuracy |
|---------|----------|
| preference_following | 85.0% |
| temporal_reasoning | 58.8% |
| instruction_following | 55.0% |
| information_extraction | 53.2% |
| knowledge_update | 50.0% |
| abstention | 47.5% |
| contradiction_resolution | 43.1% |
| multi_session_reasoning | 38.8% |
| summarization | 19.5% |
| event_ordering | 7.7% |

**Cost:** $3.41

### Chronological context (+1.9pp → 47.8%)

Sorting retrieved facts chronologically before the reader (instead of by relevance score):

| Ability | Baseline | Chrono | Δ |
|---------|----------|--------|---|
| event_ordering | 7.7% | 14.2% | +6.5 |
| contradiction_resolution | 43.1% | 51.2% | +8.1 |
| information_extraction | 53.2% | 61.4% | +8.2 |
| preference_following | 85.0% | 75.4% | −9.6 |

Chronological order helps temporal questions but buries preference signals. Next: ability-aware ordering (chrono ON for temporal abilities, OFF for preference).

### Ability-aware chrono (47.0%, -0.8pp vs global chrono)

Chrono ON for event_ordering, temporal_reasoning, contradiction_resolution, knowledge_update, information_extraction, multi_session_reasoning; OFF for preference_following, summarization, abstention, instruction_following.

**Key finding: high run-to-run variance.** Abilities with identical code paths moved ±3-7pp between runs (event_ordering -3.1, info_extraction -4.2, knowledge_update +7.5 — all chrono ON in both runs). LLM reader/judge non-determinism is the noise floor. Single-run per-ability deltas should not be over-interpreted; 2-3 repeat runs needed to separate signal from noise.
