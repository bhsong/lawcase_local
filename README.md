# lawcase_local

Answers questions about the Korean Labor Standards Act (근로기준법) and its Enforcement Decree, with a short conclusion and verbatim quotes from the cited paragraphs. Every model runs locally: the answer model on llama-server, embeddings and the reranker in PyTorch. No question leaves the machine.

> 근로기준법 질문에 결론과 근거 조문 원문으로 답합니다. 모든 모델이 로컬에서 동작하며, 질문이 외부로 나가지 않습니다.

Status: in progress (`docs/PLAN.md`, design in `docs/DESIGN.md`). v1, which used cloud models, is at [lawcase-openai](https://github.com/bhsong/lawcase-openai).

## How it works

```
question -> select articles (CONTEXT) -> answer model (JSON schema) -> verification -> answer
```

The baseline puts the whole statute in the prompt (`CONTEXT=full`). Search is then added one piece at a time, and each mode is measured against that baseline and v1:

| `CONTEXT` | articles sent to the answer model |
|---|---|
| `full` | every article of the Act and Decree |
| `keyword` | keyword search top k |
| `embedding` | Qwen3-Embedding-0.6B top k |
| `rrf` | keyword and embedding rankings merged by RRF, top N |
| `rerank` | RRF candidates rescored by Qwen3-Reranker-0.6B, top R |

- **Answer**: Qwen3.8-27B (Q4_K_M) on llama-server returns a conclusion and the paragraphs it relies on, as strict JSON.
- **Verification**: code checks that each cited paragraph exists and that numbers in the conclusion appear in the cited text or the question; one retry on failure.

## Results

Labor dev set (100 questions, 80 in scope). `correct_conclusion` is the strict accuracy. Same cases, paired by `id`.

| version | context | models | correct_conclusion | expected_cited | recall | latency | memory |
|---|---|---|---|---|---|---|---|
| v1 | retrieval | Qwen3 8B embedding and reranker, Qwen3.8-27B (OpenRouter) | 95.0% | 100% | — | — | — |
| v2 | full | Qwen3.8-27B Q4_K_M | — | — | — | — | — |
| v2 | keyword / embedding / rrf / rerank | see `docs/PLAN.md` | — | — | — | — | — |

## Setup

Developed and measured on a Mac mini (Apple silicon, 32 GB). Requires Python 3.14, [uv](https://docs.astral.sh/uv/), and [llama.cpp](https://github.com/ggml-org/llama.cpp).

```
uv sync
cp .env.example .env          # fill in LAW_OC (law.go.kr Open API ID) and LLM_MODEL
llama-server -m <model>.gguf --port 8080
uv run --env-file .env lawcase_local   # Gradio page on 127.0.0.1
```

Settings are environment variables; the full list is in `docs/DESIGN.md` §4. `.env` is read only when passed with `--env-file .env` (or with `UV_ENV_FILE=.env` set in the shell).

## Evaluation and tests

```
uv run --env-file .env python -m lawcase_local.evaluate --save NAME     # full dev run, saved
uv run --env-file .env python -m lawcase_local.evaluate --compare A B   # paired by id
uv run --env-file .env python -m lawcase_local.evaluate --recall        # search recall, no answer model
uv run pytest                                          # no network, no models
```

## Built with AI

Written with Claude Code under the rules in `CLAUDE.md`: no hardcoded statute content, no code written to pass tests, eval labels never edited to match results, tests written first by Claude, and the core search and verification code written by the author against those tests.

## Limits

- Verification is mechanical: it checks that cited parts exist and numbers match, not that the conclusion reads them correctly.
- In search modes, an article that search misses is never seen by the answer model.
- Not legal advice.

## License

MIT
