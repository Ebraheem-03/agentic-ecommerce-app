"""Support-RAG over policy prose — retrieval + citation keys (US-E5-05, ADR-0033).

DB-backed against the seeded throwaway DB (7 policy docs). The default keyword retriever
is key-free + deterministic, so these run in CI with no embedding provider. They prove the
support agent's RAG surface retrieves the RIGHT policy for a support question and emits the
golden ``source_docs`` citation key shape (``kind@store-slug`` / ``kind@platform``) so
Juno's RAGAS can resolve a live citation back to a golden expectation.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.services.rag import (
    policy_citation_key,
    product_citation_key,
    retrieve_policies,
)
from tests.conftest import SeededDb


def test_policy_citation_key_shapes() -> None:
    assert policy_citation_key("returns", None) == "returns@platform"
    assert policy_citation_key("care", "solveig-ceramics") == "care@solveig-ceramics"
    assert product_citation_key("tide-pour-over-mug") == "tide-pour-over-mug"


@pytest.mark.parametrize(
    ("query", "expected_key"),
    [
        ("What is the return window?", "returns@platform"),
        ("How long does shipping take and when is it free?", "shipping@platform"),
        ("What payment methods do you accept?", "payments@platform"),
        ("How do I care for my Solveig stoneware mug?", "care@solveig-ceramics"),
    ],
)
def test_retrieve_policies_surfaces_the_right_doc(
    seeded_db: SeededDb, query: str, expected_key: str
) -> None:
    """A support question retrieves the policy doc the golden set cites for it."""
    with Session(seeded_db.engine) as s:
        docs = retrieve_policies(s, query=query, limit=4)
    assert docs, f"no policy retrieved for {query!r}"
    keys = [d.citation_key for d in docs]
    assert expected_key in keys, f"{expected_key} not in retrieved {keys}"
    # The top hit should be the expected policy for these unambiguous questions.
    assert docs[0].citation_key == expected_key


def test_retrieved_doc_carries_quotable_snippet(seeded_db: SeededDb) -> None:
    """The grounding doc carries the policy prose (what the answer is grounded in)."""
    with Session(seeded_db.engine) as s:
        docs = retrieve_policies(s, query="return window", limit=2)
    top = docs[0]
    assert top.source_type == "policy"
    assert top.snippet().strip()
    assert top.score is not None


def test_retrieve_policies_empty_for_offtopic_query(seeded_db: SeededDb) -> None:
    """An off-topic query that matches no policy text returns nothing (agent refuses)."""
    with Session(seeded_db.engine) as s:
        docs = retrieve_policies(s, query="xyzzy quux zzzznonexistentterm", limit=4)
    assert docs == []
