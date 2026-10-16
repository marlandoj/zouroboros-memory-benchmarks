# Zouroboros Memory Benchmarks

Published benchmark results for the **Zouroboros Intelligence Plane** memory system.

## Results

| Benchmark | Score | Reader | Judge | Date |
|-----------|-------|--------|-------|------|
| LongMemEval (full S, real embeddings) | **81.5%** | gpt-5-mini | gpt-4o | 2026-10-15 |
| LongMemEval (oracle, perfect retrieval) | **84.0%** | gpt-5-mini | gpt-4o | 2026-10-15 |
| LoCoMo | **40.5%** | gpt-5-mini | gpt-4o | 2026-10-16 |
| BEAM (100K) | **45.9%** | gpt-5-mini | gpt-4o | 2026-10-16 |

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

**Evidence recall@K:** 61.0% — K=10 misses 39% of evidence. Published baselines (Mem0 92.5%, Zep 94.7%) use top-200 retrieval. Widening K is the next experiment.
**Cost:** $2.98

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
