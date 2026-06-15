"""CI-safe unit tests for the Gemini embedding provider (US-E5-04b, ADR-0032).

NO live Gemini call here — the registry resolution + the ``GeminiEmbedder`` behavior
(768-length, L2-normalized output, query-vs-document task routing) are exercised against a
FAKE client injected by monkeypatching ``GoogleGenerativeAIEmbeddings``. The default stays
``StubEmbedder`` so the rest of the suite is unaffected; these tests pin ``EMBED_PROVIDER``
/ ``GEMINI_API_KEY`` locally via monkeypatch and never touch the network.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from typing import Any

import pytest

import app.services.embeddings as emb
from app.core.config import settings
from app.services.embeddings import (
    GeminiEmbedder,
    StubEmbedder,
    _l2_normalize,
    get_embedder,
)

EMBED_DIM = settings.embed_dim  # 768 — the vector(768) column / HNSW index dim


class _FakeGeminiClient:
    """Stand-in for ``GoogleGenerativeAIEmbeddings``.

    Records the ``task_type`` / ``output_dimensionality`` each call received (so tests can
    assert query-vs-doc routing + MRL truncation), and returns a deterministic UN-normalized
    raw vector (mirrors real Gemini, whose MRL-truncated output is not unit-norm) so the
    embedder's L2-normalization is actually exercised.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.calls: list[dict[str, Any]] = []

    def _raw(self, text: str, dim: int) -> list[float]:
        # Deterministic, content-derived, and deliberately NOT unit-norm (values ~> 1).
        return [float((hash((text, i)) % 1000) + 1) for i in range(dim)]

    def embed_query(
        self,
        text: str,
        *,
        task_type: str | None = None,
        output_dimensionality: int | None = None,
    ) -> list[float]:
        dim = output_dimensionality or EMBED_DIM
        self.calls.append({"kind": "query", "task_type": task_type, "dim": dim})
        return self._raw(text, dim)

    def embed_documents(
        self,
        texts: list[str],
        *,
        task_type: str | None = None,
        output_dimensionality: int | None = None,
    ) -> list[list[float]]:
        dim = output_dimensionality or EMBED_DIM
        self.calls.append(
            {"kind": "documents", "task_type": task_type, "dim": dim, "n": len(texts)}
        )
        return [self._raw(t, dim) for t in texts]


@pytest.fixture
def gemini_embedder(monkeypatch: pytest.MonkeyPatch) -> Iterator[GeminiEmbedder]:
    """Build a ``GeminiEmbedder`` whose underlying client is the fake (no network/key)."""
    monkeypatch.setattr(settings, "gemini_api_key", "fake-key-for-tests")
    monkeypatch.setattr(settings, "embed_provider", "gemini")

    import langchain_google_genai

    monkeypatch.setattr(
        langchain_google_genai, "GoogleGenerativeAIEmbeddings", _FakeGeminiClient
    )
    yield GeminiEmbedder()


def _is_unit_norm(vector: list[float]) -> bool:
    return abs(math.sqrt(sum(c * c for c in vector)) - 1.0) < 1e-9


def test_registry_resolves_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    """``EMBED_PROVIDER=gemini`` resolves ``GeminiEmbedder`` (key present)."""
    monkeypatch.setattr(settings, "gemini_api_key", "fake-key-for-tests")
    monkeypatch.setattr(settings, "embed_provider", "gemini")
    monkeypatch.setattr(emb, "_PROVIDERS", {"stub": StubEmbedder, "gemini": GeminiEmbedder})

    import langchain_google_genai

    monkeypatch.setattr(
        langchain_google_genai, "GoogleGenerativeAIEmbeddings", _FakeGeminiClient
    )
    assert isinstance(get_embedder(), GeminiEmbedder)


def test_default_provider_is_stub() -> None:
    """The shipped default stays the stub so CI/evals are key-free (unchanged suite)."""
    assert settings.embed_provider == "stub"
    assert isinstance(get_embedder(), StubEmbedder)


def test_gemini_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selecting gemini with no key fails loud (never a silent stub fallback)."""
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        GeminiEmbedder()


def test_doc_embed_is_768_normalized_with_doc_task(gemini_embedder: GeminiEmbedder) -> None:
    vector = gemini_embedder.embed_text("Insulated waterproof leather hiking boot.")
    assert len(vector) == EMBED_DIM == 768
    assert _is_unit_norm(vector)
    client = gemini_embedder._client
    assert isinstance(client, _FakeGeminiClient)
    assert client.calls[-1]["task_type"] == "RETRIEVAL_DOCUMENT"
    assert client.calls[-1]["dim"] == EMBED_DIM


def test_batch_embed_is_768_normalized_with_doc_task(
    gemini_embedder: GeminiEmbedder,
) -> None:
    vectors = gemini_embedder.embed_batch(["alpha blurb", "beta blurb", "gamma blurb"])
    assert len(vectors) == 3
    assert all(len(v) == EMBED_DIM for v in vectors)
    assert all(_is_unit_norm(v) for v in vectors)
    client = gemini_embedder._client
    assert isinstance(client, _FakeGeminiClient)
    assert client.calls[-1] == {
        "kind": "documents",
        "task_type": "RETRIEVAL_DOCUMENT",
        "dim": EMBED_DIM,
        "n": 3,
    }


def test_query_embed_is_768_normalized_with_query_task(
    gemini_embedder: GeminiEmbedder,
) -> None:
    """The query path routes RETRIEVAL_QUERY — the asymmetric-retrieval seam."""
    vector = gemini_embedder.embed_query("waterproof hiking boots for cold weather")
    assert len(vector) == EMBED_DIM
    assert _is_unit_norm(vector)
    client = gemini_embedder._client
    assert isinstance(client, _FakeGeminiClient)
    assert client.calls[-1]["task_type"] == "RETRIEVAL_QUERY"


def test_gemini_model_tag_is_real_model_id(gemini_embedder: GeminiEmbedder) -> None:
    """``model`` is the resolved Gemini id (attributable rows), not the stub tag."""
    assert gemini_embedder.model == settings.embed_model
    assert gemini_embedder.model != "seed-stub"


def test_stub_query_path_is_noop_default() -> None:
    """Stub keeps a no-op ``embed_query`` (== ``embed_text``): key-free, deterministic."""
    stub = StubEmbedder()
    text = "no asymmetry for the stub"
    assert stub.embed_query(text) == stub.embed_text(text)


def test_l2_normalize_unit_and_zero_safe() -> None:
    assert _is_unit_norm(_l2_normalize([3.0, 4.0]))  # 3-4-5 -> [0.6, 0.8]
    assert _l2_normalize([0.0, 0.0, 0.0]) == [0.0, 0.0, 0.0]  # no divide-by-zero
