# lawcase_local

Answers questions about a Korean law (an Act and its Enforcement Decree) with verbatim quotes from the cited articles. Every model runs on this machine: embeddings and the reranker in PyTorch inside the app, the answer model on a local OpenAI-compatible server (llama-server). v1 (cloud and OpenRouter models) is archived at [lawcase-openai](https://github.com/bhsong/lawcase-openai); its results are the baseline. Steps and decision log: `docs/PLAN.md`. Design (modules, settings, formats, answer contract): `docs/DESIGN.md`. Keep all docs in `docs/`.

## Commands

```
uv run --env-file .env lawcase_local          # run the Gradio app
uv run pytest                                 # tests (no network, no models)
uv run ruff check && uv run ruff format       # lint and format
uv run --env-file .env python -m lawcase_local.evaluate ...   # evaluation (runs local models)
```

## Purpose: the user learns by building

- The user writes the core retrieval and verification code (keyword search, RRF, verification). For those, explain, review, and suggest; write code only when asked.
- Every change comes with a short explanation of why, so the user can explain it without help.

## Tests first

- For every item, Claude writes the tests first, before any implementation, including for the code the user writes.
- Run them and show that they fail for the right reason (missing function or wrong behavior, not a broken test). Then the user approves the tests before implementation starts.
- Tests describe observable behavior from the plan item, with small made-up articles and questions, never eval questions.
- Once approved, tests change only when the plan item changes; say what changed and why.

## Simplicity first

- Write the least code that works. Plain functions and the standard library; no classes or layers until they remove real duplication.
- Latest stable Python and libraries, added with `uv add`. Add a dependency only when it clearly replaces more code than it costs.
- No vector database or morphological analyzer unless a plan step calls for it and the user approves.
- The model judges (scope, relevant articles); code checks only what is mechanical.

## Local only

- No model call leaves this machine. The only network calls are fetching statutes from law.go.kr (`LAW_OC`) and downloading model weights.
- The answer model is reached through the OpenAI-compatible Chat Completions API with a strict JSON schema; its URL and model name are settings.
- Model names, devices, k values, and timeouts live in `config.py` settings (env vars).

## No hardcoding

- No word lists, synonym maps, regexes, or branches aimed at particular questions.
- No statute content (amounts, periods, rates, conditions) in code or prompts. Every fact comes from the corpus.
- Prompt examples, if any, use made-up articles unrelated to the eval questions.

## No code written just to pass tests

- Code must not detect test inputs or eval questions.
- Do not loosen assertions, change expected values to match output, or skip tests.
- A bug-fix test must fail on the old code; report that it did.
- Tests never load real models; use fakes.

## Evaluation

- Dev set: `eval/dev-labor.jsonl` (same as v1). The holdout set lives outside this repo; never look for it or ask for it.
- Never edit eval labels to match results. Report suspected label errors with the statute text.
- Metric definitions match v1 so results compare; add new metrics instead of changing old ones.
- Compare settings on the same cases, paired by `id`. Record memory and latency with every run.

## Workflow

- Follow `docs/PLAN.md` step by step. When a step is done, tick it and record numbers in its decision log.
- One branch per step (`step-N-<name>`). After each item, tests and ruff pass, then commit that item alone.
- When a step is done, report: files changed, test results, metrics, open issues, and how the user can check it.
- Never push, open a PR, or merge without the user's approval.
- Secrets (`LAW_OC`) stay in `.env`; never in code, logs, fixtures, or commits.
