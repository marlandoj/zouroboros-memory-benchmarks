# Zouroboros Memory Benchmarks

Published benchmark results for the **Zouroboros Intelligence Plane** memory system.

## Results

| Benchmark | Score | Reader | Judge | Date |
|-----------|-------|--------|-------|------|
| LongMemEval (full S, real embeddings) | **81.5%** | gpt-5-mini | gpt-4o | 2026-10-15 |
| LongMemEval (oracle, perfect retrieval) | **84.0%** | gpt-5-mini | gpt-4o | 2026-10-15 |
| LoCoMo | *running* | gpt-5-mini | gpt-4o | — |
| BEAM (128K) | *running* | gpt-5-mini | gpt-4o | — |

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
