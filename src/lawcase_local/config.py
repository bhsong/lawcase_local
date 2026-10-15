import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

CONTEXTS = ("full", "keyword", "embedding", "rrf", "rerank")


@dataclass(frozen=True)
class Settings:
    law_oc: str | None = field(repr=False)
    act: str
    data_dir: Path
    llm_url: str
    llm_model: str
    llm_timeout_s: int
    max_retries: int
    context: str
    keyword_k: int
    embedding_k: int
    rrf_c: int
    rrf_n: int
    rerank_top: int
    embedding_model: str
    rerank_model: str
    device: str


def _required(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "")
    if not value:
        raise SystemExit(f"missing setting: {name}")
    return value


def _int(env: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(env.get(name, default))
    except ValueError:
        raise SystemExit(f"{name} must be an integer") from None


def load_settings(env: Mapping[str, str] = os.environ) -> Settings:
    context = env.get("CONTEXT", "full")
    if context not in CONTEXTS:
        raise SystemExit(f"CONTEXT must be one of: {', '.join(CONTEXTS)}")

    return Settings(
        law_oc=env.get("LAW_OC") or None,
        act=env.get("ACT", "근로기준법"),
        data_dir=Path(env.get("DATA_DIR", "data")),
        llm_url=env.get("LLM_URL", "http://127.0.0.1:8080/v1"),
        llm_model=_required(env, "LLM_MODEL"),
        llm_timeout_s=_int(env, "LLM_TIMEOUT_S", 600),
        max_retries=_int(env, "MAX_RETRIES", 1),
        keyword_k=_int(env, "KEYWORD_K", 10),
        embedding_k=_int(env, "EMBEDDING_K", 10),
        rrf_c=_int(env, "RRF_C", 60),
        rrf_n=_int(env, "RRF_N", 15),
        rerank_top=_int(env, "RERANK_TOP", 10),
        embedding_model=env.get("EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B"),
        rerank_model=env.get("RERANK_MODEL", "Qwen/Qwen3-Reranker-0.6B"),
        device=env.get("DEVICE", "mps"),
        context=context,
    )
