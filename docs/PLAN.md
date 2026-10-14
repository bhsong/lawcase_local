# Plan: lawcase_local (v2), local only

## Goal

Rebuild the v1 pipeline so that every model runs on this machine, with the core code written by the user. Start from a baseline with no search (the whole statute in the prompt), then add search one piece at a time and measure each against that baseline and v1. Embeddings and the reranker run in PyTorch inside the app, so later fine-tuning can happen in the same codebase. Design: `docs/DESIGN.md`.

## Starting point

- v1 ([lawcase-openai](https://github.com/bhsong/lawcase-openai)), Labor Standards Act (근로기준법) dev set, 100 cases, 80 in scope:
  - all API (Qwen3-Embedding-8B, Qwen3-Reranker-8B, Qwen3.8-27B): correct_conclusion 95.0%, expected_cited 100%.
  - local embeddings (4B Q4) and local reranker (0.6B Q4), API answer model: one case short of the 8B reranker on recall.
  - v1 also had `CONTEXT=full` (whole statute in the prompt); on the housing-lease set, retrieval lost to full only where search missed the expected articles.
- Hardware: v2 is developed and measured on the Mac mini (32 GB), from step 0. The answer model is Qwen3.8-27B Q4_K_M (about 16.5 GB) on llama-server; the rest of memory holds the KV cache for the full statute and the PyTorch models.

## Eval

`eval/dev-labor.jsonl` (copied from v1, labels unchanged). Each case: `id`, `question`, `kind` (`in_scope` or `out_of_scope`), `expected` (article ids), `must_include` (a list of groups, each a list of alternatives), `style`.

Metric definitions match v1 `evaluate.py`, so results compare. Matching ignores all whitespace.

- `conclusion_hit`: every `must_include` group has at least one alternative in the conclusion alone (groups AND, alternatives OR).
- `content_hit`: the same check on the conclusion plus the cited quotes.
- `correct_conclusion` (strict, the headline): in-scope cases with `must_include` that are answered with `conclusion_hit`.
- `correct_answer`: the same cases, answered with `content_hit`.
- `expected_cited`: in-scope cases whose cited article ids share at least one id with `expected`.
- `out_of_scope_answered`: out-of-scope cases that got an answer instead of a refusal.
- `retrieval_recall@k`: in-scope cases whose `expected` articles are all in the top k (no answer model call).
- Peak memory and latency per question, per stage.

An answer that fails verification or is refused counts as wrong. `must_not_include` is not ported: the labor dev set has none, so v1 numbers are unaffected.

Every run is saved and added as one row to the results table (step 11): context mode, models, the metrics above.

## Steps

Each step starts on its own branch and ends with `uv run pytest` and `ruff` passing. Every item starts with tests written by Claude, shown failing and approved by the user; then the implementation (by the user where marked).

### 0. Skeleton
- [ ] uv project, `config.py` settings (env vars), ruff, pytest, GitHub Actions CI. A missing required setting exits with its name, never its value.

### 1. Corpus
- [ ] Fetch the Act and Decree from law.go.kr (`LAW_OC`); save raw responses without the OC value.
- [ ] Build `data/<Act name>/corpus.jsonl`, one article per line, ids in v1's format (`근로기준법 제11조`, `근로기준법시행령 제2조`).
- [ ] Report article count and total tokens of the statute prompt (with the answer model's tokenizer through llama-server).
- [ ] Copy `eval/dev-labor.jsonl` from v1; a check that every expected article exists in the corpus.

### 2. Eval harness
- [ ] `evaluate.py` scoring and metrics as defined above, tested with a fake answer function; no model needed.
- [ ] `--save NAME` writes every record plus run settings; `--compare A B` pairs by `id` (newly right, newly wrong).
- [ ] Latency per stage and peak memory recorded per question.
- [ ] If v1's saved result for the labor set is available, a loader so `--compare` can take it.

### 3. Full-context baseline
- [ ] Answer through llama-server (Chat Completions, strict JSON schema) with the whole statute in a fixed prefix and the question last, so the server reuses the cached prefix.
- [ ] Check that llama-server's context size covers the statute prompt (step 1's token count) plus the answer; record the size and llama-server's memory.
- [ ] Full dev run with Qwen3.8-27B Q4_K_M; record metrics, latency (first question apart from the rest), memory.

### 4. Verification (written by the user)
- [ ] Cited articles and parts exist; numbers in the conclusion appear in the cited text or the question; one retry with the reasons.
- [ ] Rerun the baseline; report how many answers verification failed, fixed on retry, or turned from right to wrong.

### 5. Gradio app
- [ ] One page: question, mode badge, conclusion, cited parts verbatim; context mode is a setting. For looking at answers, not for scoring.

### 6. Keyword search (written by the user)
- [ ] Keyword index and search; `evaluate --recall` at k = 3, 5, 10.
- [ ] Context mode `keyword`: only the top k articles go to the answer model; full dev run next to the baseline.

### 7. Embedding search
- [ ] Qwen3-Embedding-0.6B in PyTorch (MPS): embed the corpus once (saved with model name and text hash), questions per ask.
- [ ] Recall vs keyword; memory and time per question; context mode `embedding` dev run.

### 8. RRF (written by the user)
- [ ] Merge keyword and embedding rankings; recall of the merged top N; context mode `rrf` dev run.

### 9. Reranker
- [ ] Qwen3-Reranker-0.6B in PyTorch scores the RRF candidates; top 10 go on.
- [ ] Recall at top 5 and 10 vs v1's local reranker; context mode `rerank` dev run.

### 10. Search misses
- [ ] For every case the best search mode gets wrong but full context gets right: were the expected articles retrieved? Decide k and N from answers, not recall alone.

### 11. Results table
- [ ] README table: full context vs each search mode vs v1 — correct_conclusion, expected_cited, recall, latency, memory. Same cases, paired by `id`.

Later plans (separate files): fine-tuning the reranker and embeddings, the router, more laws.

## Decision log

| date | decision | why |
|---|---|---|
| 2026-10-14 | Eval checks only `must_include`; `must_not_include` is not ported | the labor dev set has none, so v1 results compare unchanged; less code |
| 2026-10-14 | Order: corpus → eval → full-context baseline → verification → app → search one piece at a time | each search step is measured against a no-search baseline; eval exists before any model runs |
| 2026-10-14 | Gradio instead of FastAPI and a hand-written page | a working UI in a few lines; the app is for looking at answers, eval is the measure |
| 2026-10-14 | Develop v2 on the Mac mini (32 GB) only | the 27B answer model and a full-statute KV cache do not fit in 8 GB; one machine keeps latency and memory comparable across runs |
