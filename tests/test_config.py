from pathlib import Path

import pytest

from lawcase_local.config import load_settings

REQUIRED = {"LLM_MODEL": "test-model"}


def test_defaults_when_only_required_settings_are_set():
    s = load_settings(REQUIRED)

    assert s.law_oc is None
    assert s.act == "근로기준법"
    assert s.data_dir == Path("data")
    assert s.llm_url == "http://127.0.0.1:8080/v1"
    assert s.llm_model == "test-model"
    assert s.llm_timeout_s == 600
    assert s.max_retries == 1
    assert s.context == "full"
    assert s.keyword_k == 10
    assert s.embedding_k == 10
    assert s.rrf_c == 60
    assert s.rrf_n == 15
    assert s.rerank_top == 10
    assert s.embedding_model == "Qwen/Qwen3-Embedding-0.6B"
    assert s.rerank_model == "Qwen/Qwen3-Reranker-0.6B"
    assert s.device == "mps"


def test_env_vars_override_defaults_and_numbers_become_ints():
    env = {
        "LAW_OC": "made-up-oc",
        "ACT": "가상법",
        "DATA_DIR": "/tmp/somewhere",
        "LLM_URL": "http://127.0.0.1:9999/v1",
        "LLM_MODEL": "other-model",
        "LLM_TIMEOUT_S": "30",
        "MAX_RETRIES": "0",
        "CONTEXT": "rrf",
        "KEYWORD_K": "3",
        "EMBEDDING_K": "4",
        "RRF_C": "10",
        "RRF_N": "7",
        "RERANK_TOP": "5",
        "EMBEDDING_MODEL": "org/embed",
        "RERANK_MODEL": "org/rerank",
        "DEVICE": "cpu",
    }

    s = load_settings(env)

    assert s.law_oc == "made-up-oc"
    assert s.act == "가상법"
    assert s.data_dir == Path("/tmp/somewhere")
    assert s.llm_url == "http://127.0.0.1:9999/v1"
    assert s.llm_model == "other-model"
    assert s.llm_timeout_s == 30
    assert s.max_retries == 0
    assert s.context == "rrf"
    assert s.keyword_k == 3
    assert s.embedding_k == 4
    assert s.rrf_c == 10
    assert s.rrf_n == 7
    assert s.rerank_top == 5
    assert s.embedding_model == "org/embed"
    assert s.rerank_model == "org/rerank"
    assert s.device == "cpu"


def test_reads_process_environment_by_default(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "from-environ")

    assert load_settings().llm_model == "from-environ"


@pytest.mark.parametrize("env", [{}, {"LLM_MODEL": ""}])
def test_missing_llm_model_exits_with_its_name(env):
    with pytest.raises(SystemExit) as exc:
        load_settings(env)

    assert "LLM_MODEL" in str(exc.value)


def test_law_oc_is_optional_when_loading_settings():
    assert load_settings(REQUIRED).law_oc is None


@pytest.mark.parametrize(
    "name",
    ["LLM_TIMEOUT_S", "MAX_RETRIES", "KEYWORD_K", "EMBEDDING_K", "RRF_C", "RRF_N", "RERANK_TOP"],
)
def test_non_integer_exits_with_name_but_not_value(name):
    bad = "secret-looking-value"

    with pytest.raises(SystemExit) as exc:
        load_settings(REQUIRED | {name: bad})

    assert name in str(exc.value)
    assert bad not in str(exc.value)


@pytest.mark.parametrize("mode", ["full", "keyword", "embedding", "rrf", "rerank"])
def test_every_context_mode_is_accepted(mode):
    assert load_settings(REQUIRED | {"CONTEXT": mode}).context == mode


def test_unknown_context_exits_with_name_but_not_value():
    bad = "secret-looking-value"

    with pytest.raises(SystemExit) as exc:
        load_settings(REQUIRED | {"CONTEXT": bad})

    assert "CONTEXT" in str(exc.value)
    assert bad not in str(exc.value)


def test_law_oc_value_is_not_in_repr():
    s = load_settings(REQUIRED | {"LAW_OC": "made-up-oc"})

    assert "made-up-oc" not in repr(s)
