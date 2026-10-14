# Design: lawcase_local (v2)

How the parts fit, what each one takes and returns, and the formats on disk. The order of work is in `docs/PLAN.md`; the rules are in `CLAUDE.md`. Where v1 already settled something, v2 keeps it so results compare.

## 1. Scope

- One law at a time: an Act and its Enforcement Decree (근로기준법 first). Code takes the Act name from settings and has nothing specific to it.
- Every model runs on this machine: a Mac mini with 32 GB, Apple silicon (MPS for PyTorch, Metal for llama-server). The only network calls fetch statutes from law.go.kr and download model weights.
- Not in v2: the router, supplementary provisions (부칙), several laws at once, fine-tuning (a later plan).

## 2. Data flow

```
once      law.go.kr ──► data/raw/*.json ──► data/<Act>/corpus.jsonl
                                               │
                                               ├─► keyword index        (step 6)
                                               └─► embeddings.npz       (step 7)

per ask   question
            │
            ▼
          select articles ── CONTEXT=full    : all articles
            │                 keyword        : keyword top k
            │                 embedding      : embedding top k
            │                 rrf            : RRF of both, top N
            │                 rerank         : reranker over RRF top N, top R
            ▼
          answer model (llama-server, strict JSON schema)
            │
            ▼
          verify ──fail──► retry once with reasons
            │
            ▼
          result (mode, conclusion, citations with quotes, timings)
            │
            ├─► Gradio page
            └─► evaluate.py (score, save, compare)
```

Selected articles always go to the prompt in corpus order, not score order, so the same articles give the same prompt.

## 3. Modules

Plain functions in `src/lawcase_local/`. One module per row; ★ = written by the user.

| module | job | main functions |
|---|---|---|
| `config.py` | settings from env vars | `load_settings()` |
| `lawdata.py` | fetch and parse statutes, build the corpus | `fetch_law(oc, name)`, `parse_law(raw)`, `build(settings)`, `load_corpus(settings)` |
| `prompt.py` | instructions, statute text, JSON schema, retry message | `prefix(articles, retrieval)`, `schema(articles)`, `retry_input(question, reply, reasons)` |
| `llm.py` | one Chat Completions call to llama-server | `complete(settings, system, user, schema) -> (text, usage)`, `count_tokens(settings, text)` |
| `verify.py` ★ | mechanical checks on an answer | `parts(article)`, `verify(reply, articles_by_id, question) -> list[str]` |
| `answer.py` | select, call, verify, retry | `ask(settings, articles, question, search=None) -> dict` |
| `keyword.py` ★ | keyword index and search | `index(articles)`, `search(idx, question, k) -> list[id]` |
| `embed.py` | Qwen3-Embedding-0.6B in PyTorch | `load_or_build(settings, articles)`, `search(emb, question, k) -> list[id]` |
| `rrf.py` ★ | merge rankings | `merge(rankings, c, n) -> list[id]` |
| `rerank.py` | Qwen3-Reranker-0.6B in PyTorch | `rerank(settings, question, articles, top) -> list[id]` |
| `retrieve.py` | pick articles for a context mode | `select(settings, question, articles, index) -> (ids, seconds)` |
| `evaluate.py` | score, metrics, save, compare, recall | CLI, see §9 |
| `app.py` | Gradio page | `main()` |

`retrieve.py` and `rerank.py` appear in steps 6–9; until then `answer.ask` uses every article.

## 4. Settings (`config.py`)

| env var | default | meaning |
|---|---|---|
| `LAW_OC` | required for fetching | law.go.kr Open API ID; never logged or saved |
| `ACT` | `근로기준법` | Act name; the Decree is `<ACT> 시행령` |
| `DATA_DIR` | `data` | raw responses and corpora |
| `LLM_URL` | `http://127.0.0.1:8080/v1` | llama-server base URL |
| `LLM_MODEL` | required | model name sent to the server and saved with results |
| `LLM_TIMEOUT_S` | `600` | per call; full context is slow on first call |
| `MAX_RETRIES` | `1` | retries after failed verification |
| `CONTEXT` | `full` | `full`, `keyword`, `embedding`, `rrf`, `rerank` |
| `KEYWORD_K`, `EMBEDDING_K` | `10`, `10` | top k per search |
| `RRF_C`, `RRF_N` | `60`, `15` | RRF constant and how many merged ids go on |
| `RERANK_TOP` | `10` | ids kept after reranking |
| `EMBEDDING_MODEL`, `RERANK_MODEL` | `Qwen/Qwen3-Embedding-0.6B`, `Qwen/Qwen3-Reranker-0.6B` | Hugging Face ids |
| `DEVICE` | `mps` | PyTorch device (`cpu` in CI) |

k and N defaults come from v1 and get revisited in step 10.

## 5. Corpus format

`data/raw/<name without spaces>.json`: the lawService.do response as received, with the OC value removed.

`data/<Act>/corpus.jsonl`: one article per line, same fields and ids as v1's `corpus.json` so dev labels match.

```json
{"id": "근로기준법 제11조", "law_name": "근로기준법", "article": "제11조", "title": "적용 범위",
 "body": "① 이 법은 ...\n② ...", "history": ["① 개정 2008. 3. 21."], "effective_date": "2021-11-19"}
```

- `id`: law name without spaces + article (`근로기준법시행령 제7조의2`). Unique across Act and Decree.
- `body`: statute text only, one paragraph, item or sub-item per line, starting with its marker (①, 1., 가.). The article heading and amendment notes are removed; notes move to `history`.
- Deleted articles (no title) are skipped.
- `data/<Act>/meta.json`: article count, characters, prompt tokens of the full statute, effective dates, build time.

Paragraph and item labels are not stored; `verify.parts` derives them from line markers, as in v1.

## 6. Answer contract

**Request.** System message = `prompt.prefix(articles, retrieval)`: instructions, then every selected article as `[id] title\nbody`. User message = the question (or the retry message). With `CONTEXT=full` the system message is byte-identical for every question, so llama-server reuses its cached prefix; nothing variable goes before the question.

**Schema** (strict, as v1):

```json
{"status": "answered | out_of_scope | insufficient",
 "conclusion": "1–3 sentences",
 "citations": [{"article_id": "<enum of selected ids>", "parts": ["②", "②3"]}],
 "unanswered": ""}
```

`article_id` and `parts` are enums built from the selected articles, so the model cannot name an id or label outside them.

**Result** of `answer.ask`:

| field | meaning |
|---|---|
| `mode` | `answered`, `out_of_scope`, `insufficient`, `verify_failed`, `unavailable` |
| `conclusion`, `unanswered` | from the model |
| `citations` | `article_id`, resolved `parts`, `quote` (corpus text of those parts) |
| `reasons` | verification failures of the last attempt |
| `retries` | 0 or 1 |
| `selected` | article ids sent to the model (all ids in full mode) |
| `usage` | prompt, cached, completion tokens as the server reports them |
| `seconds` | per stage: `search`, `rerank`, `answer`; plus `total` |

`unavailable` = server error, timeout, or output that is not valid JSON for the schema.

## 7. Verification (★)

Same rules as v1 `verify.py`; the user writes it against tests.

- `out_of_scope` passes without checks.
- `answered` needs at least one citation.
- Each cited article exists among the selected ones; each label exists in it. An article with paragraphs needs labels; one without paragraphs may be cited whole. A bare item number (`3`) means that item of the only paragraph that has it.
- Every number in the conclusion, other than 제N조/항/호 references, appears by value (4천800만 = 4,800만) in the cited parts or the question.
- Failure → one retry: the question, the failed answer, and the reasons after the same prefix.

What it cannot catch: a conclusion that misreads a cited paragraph, and an article that selection left out.

## 8. Search (steps 6–9)

All searches take the question and return article ids, best first.

- **Keyword ★**: the user's design (tokens, weighting). No morphological analyzer unless a step approves one.
- **Embedding**: Qwen3-Embedding-0.6B with its query instruction; article text = `title + body`. Vectors saved to `embeddings.npz` with model name and a hash of each text; rebuilt when either changes. Cosine similarity.
- **RRF ★**: score(id) = Σ over rankings 1 / (c + rank), rank from 1; ids missing from a ranking add nothing. Keep the top N.
- **Reranker**: Qwen3-Reranker-0.6B scores (question, article) pairs for the RRF candidates; keep the top R.

`evaluate --recall` runs the searches alone (no answer model) and reports recall at k = 3, 5, 10.

## 9. Evaluation

```
uv run python -m lawcase_local.evaluate --save NAME [--limit N]   # dev run, saved
uv run python -m lawcase_local.evaluate --compare A B             # paired by id
uv run python -m lawcase_local.evaluate --recall                  # searches only
```

`eval/results/NAME.json` (git-ignored):

```json
{"meta": {"started": "...", "context": "full", "llm_model": "...", "embedding_model": null,
          "rerank_model": null, "k": {...}, "prompt_hash": "...", "corpus_hash": "...",
          "git_commit": "...", "git_dirty": false, "machine": "Mac mini 32GB"},
 "records": [{"id": "l001", "kind": "in_scope", "expected": [...], "mode": "answered",
              "conclusion": "...", "citations": [...], "selected": [...],
              "conclusion_hit": true, "content_hit": true, "expected_cited": true,
              "seconds": {...}, "peak_rss_mb": 812}]}
```

- Metrics are computed from records, so labels or metric code can change and old results be rescored without model calls.
- Memory: peak RSS of the app process (PyTorch models live there). llama-server's memory is read from its own process and recorded per run, with its context size.
- Latency: the first question of a full-context run is reported apart from the rest (cold prefix cache).

## 10. Gradio app

One `gr.Blocks` page: question box, mode badge, conclusion, one card per citation with the quoted parts, and the selected article ids and seconds per stage in a collapsed panel. Context mode comes from settings. Runs at `uv run lawcase_local` on 127.0.0.1.

## 11. Testing

- No network and no models in tests: fake `llm.complete`, fake embedding and reranker functions returning fixed vectors and scores.
- Small made-up articles and questions; never dev questions.
- Fixtures: a trimmed raw law.go.kr response for `parse_law`.

## 12. Open questions

- Total prompt tokens of the Act and Decree, and whether the 27B model's context and the Mac mini's memory hold them with the PyTorch models loaded (step 1 measures tokens; step 3 sets llama-server's context size).
- Does the local llama-server build accept strict JSON schema with large enums (all article ids) without slowing down? Checked in step 3.
- Is v1's saved labor result still on disk, for `--compare` against v1?
