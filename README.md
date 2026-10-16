# Zouroboros Memory Benchmarks

Published benchmark results for the **Zouroboros Intelligence Plane** memory system.

## Results

| Benchmark | Score | Reader | Judge | Date |
|-----------|-------|--------|-------|------|
| LongMemEval (full S, real embeddings) | **81.5%** | gpt-5-mini | gpt-4o | 2026-10-15 |
| LongMemEval (oracle, perfect retrieval) | **84.0%** | gpt-5-mini | gpt-4o | 2026-10-15 |
| LoCoMo | **40.7%** (K=100) | gpt-5-mini | gpt-4o | 2026-10-16 |
| BEAM (100K) | **47.8%** (chrono) | gpt-5-mini | gpt-4o | 2026-10-16 |

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
