"""Merchandising agent — DRAFT listing + comparables price suggestion (US-E5-08, ADR-0034 §3).

The merchandising agent helps a SELLER draft a product listing. It:

  1. retrieves REAL comparable catalog rows (same-category / similar products via the
     retrieval seam — the same ``search_products`` path the shopping agent uses), so the
     listing copy and the price suggestion are grounded, never invented;
  2. generates the listing COPY (title/description/attributes) via the injectable
     ``MerchBrain`` (mirrors ``SupportBrain``; CI runs key-free with a stub);
  3. computes a PRICE SUGGESTION structurally — the median of the comparables' lowest
     active variant prices — surfaced WITH its basis (the comparable rows + the rule), so
     the seller sees why the number is what it is. No invented competitor data;
  4. persists the result as a DRAFT product (``status='draft'``) + a draft variant at the
     suggested price. It NEVER publishes to the live catalog — a seller approves first
     (the publish action is a future story; the draft + ``status`` is that seam). This
     mirrors the checkout ``interrupt()`` / refund-HITL human-in-the-loop stance.

GUARDRAIL-FIRST (ADR-0034 §3): the caller scans the seller's brief AND the retrieved
comparable passages for injection BEFORE generation; identity/scope (the seller's store)
come from request context, never from model output.

ASYNC (the story): ``generate_merch_draft_async`` runs generation off the request's
critical path on a fresh session; the draft is retrievable once ready. The node kicks it
off and returns immediately with a "draft is being prepared" acknowledgement.
"""

from __future__ import annotations

import logging
import statistics
import uuid
from concurrent.futures import Future, ThreadPoolExecutor

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.brains import MerchBrain, MerchListing
from app.db.models import Policy, Product, Variant
from app.schemas.agent import ComparableOut, MerchDraftOut, PriceSuggestionOut
from app.schemas.enums import ProductStatus
from app.services import search as search_service
from app.services.embeddings import refresh_product_embedding

_log = logging.getLogger(__name__)

# How many comparable products to ground the listing + price suggestion in.
_COMPARABLES_LIMIT = 5

# A single shared worker pool so async generation runs off the request critical path
# without spawning an unbounded number of threads.
_POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="merch")


# --------------------------------------------------------------------------- #
# Comparables + price suggestion (grounded in REAL catalog rows).               #
# --------------------------------------------------------------------------- #
def _lowest_active_price(session: Session, product_id: str) -> int | None:
    """The cheapest ACTIVE variant price for a product (minor units), or None."""
    return session.scalar(
        select(func.min(Variant.price_minor)).where(
            Variant.product_id == product_id, Variant.is_active.is_(True)
        )
    )


def find_comparables(
    session: Session, *, brief: str, exclude_store_id: str | None = None
) -> list[ComparableOut]:
    """Retrieve real same-category / similar catalog rows to ground the draft.

    Uses the live catalog retrieval seam (``search_products`` — keyword today, hybrid under
    a real embedder; ADR-0027/0032) on the seller's brief. Each comparable carries its
    lowest active variant price so the suggestion's basis is real. ``exclude_store_id``
    optionally drops the seller's own catalog from the basis; by default the seller's
    existing line IS a legitimate comparable (pricing a new mug against your mug line), so
    the node does not exclude it — there's no invented competitor data either way.
    """
    out: list[ComparableOut] = []
    seen: set[str] = set()
    # The catalog keyword retriever ANDs the query terms (``websearch_to_tsquery``), which is
    # too strict for a natural-language brief. So we search the brief's SALIENT terms one at a
    # time and union the hits — a product matching ANY distinctive term is a comparable (the
    # same OR-relaxation the policy RAG uses). Ordering preserves first-seen relevance.
    for term in _salient_terms(brief) or [brief]:
        env = search_service.search_products(
            session, q=term, category=None, cursor=None, limit=_COMPARABLES_LIMIT * 2
        )
        for result in env.data:
            product = session.get(Product, result.product.id)
            if product is None or product.id in seen:
                continue
            if exclude_store_id is not None and product.store_id == exclude_store_id:
                continue
            price = _lowest_active_price(session, product.id)
            if price is None:
                continue
            seen.add(product.id)
            out.append(
                ComparableOut(
                    product_id=product.id,
                    title=product.title,
                    slug=product.slug,
                    price_minor=price,
                )
            )
            if len(out) >= _COMPARABLES_LIMIT:
                return out
    return out


# Trivial words that add no retrieval signal — dropped so a natural-language brief's
# distinctive terms drive the comparable search (mirrors rag._STOPISH).
_STOPISH = frozenset(
    {"a", "an", "the", "new", "help", "me", "list", "for", "my", "to", "i", "want",
     "with", "and", "of", "please", "create", "draft", "make", "selling", "sell"}
)


def _salient_terms(brief: str) -> list[str]:
    """The distinctive lowercase terms of a brief (stop-ish words dropped), order-preserving."""
    import re

    out: list[str] = []
    for word in re.split(r"\W+", brief.lower()):
        if word and word not in _STOPISH and word not in out:
            out.append(word)
    return out


def suggest_price(comparables: list[ComparableOut]) -> PriceSuggestionOut:
    """Compute a price suggestion from real comparables — surfaced WITH its basis.

    The number is the MEDIAN of the comparables' lowest active variant prices (a robust
    central estimate, computed structurally — never invented by the model). No comparables
    -> no suggestion (null price), with the basis saying so. The comparable rows ride along
    so the seller can see exactly what the number was derived from.
    """
    if not comparables:
        return PriceSuggestionOut(
            suggested_price_minor=None,
            basis="No comparable catalog products found, so no price is suggested.",
            comparables=[],
        )
    prices = sorted(c.price_minor for c in comparables)
    median = int(statistics.median(prices))
    basis = (
        f"Median of {len(prices)} comparable product"
        f"{'s' if len(prices) != 1 else ''} "
        f"(prices {prices[0] / 100:.2f}–{prices[-1] / 100:.2f})."
    )
    return PriceSuggestionOut(
        suggested_price_minor=median, basis=basis, comparables=comparables
    )


# --------------------------------------------------------------------------- #
# Draft persistence — DRAFT product, NEVER published.                           #
# --------------------------------------------------------------------------- #
def _draft_slug(title: str) -> str:
    """A unique, draft-tagged slug (uuid suffix avoids colliding with live products)."""
    import re

    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "draft"
    return f"{base[:48]}-draft-{uuid.uuid4().hex[:8]}"


def persist_draft(
    session: Session,
    *,
    store_id: str,
    listing: MerchListing,
    suggestion: PriceSuggestionOut,
) -> MerchDraftOut:
    """Persist the generated listing as a DRAFT product (+ draft variant). NEVER published.

    The product is created with ``status='draft'`` — it does NOT appear in the live catalog
    (the catalog read path filters to ``status='active'``). A draft variant carries the
    suggested price (or 0 when there's no suggestion). The embedding is refreshed through
    the same write path live products use, so an approved draft is immediately searchable.
    Seller approval (flip to ``active``) is a future story — this is the draft + status seam.
    """
    product = Product(
        store_id=store_id,
        title=listing.title,
        slug=_draft_slug(listing.title),
        description=listing.description,
        category=listing.category or None,
        attributes={k: str(v) for k, v in listing.attributes.items()},
        status=ProductStatus.draft.value,
    )
    session.add(product)
    session.flush()  # assign the draft product id

    price = suggestion.suggested_price_minor or 0
    variant = Variant(
        product_id=product.id,
        sku=f"DRAFT-{uuid.uuid4().hex[:10].upper()}",
        options={},
        price_minor=price,
        currency=suggestion.currency,
        is_active=True,
    )
    session.add(variant)
    session.flush()

    # Keep the draft searchable-once-approved via the same refresh path live writes use.
    refresh_product_embedding(session, product.id)
    session.flush()

    return MerchDraftOut(
        draft_product_id=product.id,
        title=listing.title,
        description=listing.description,
        category=listing.category,
        attributes={k: str(v) for k, v in listing.attributes.items()},
        price_suggestion=suggestion,
    )


# --------------------------------------------------------------------------- #
# Generation orchestration (sync core + async wrapper).                         #
# --------------------------------------------------------------------------- #
def generate_merch_draft(
    session: Session,
    *,
    brief: str,
    store_id: str,
    brain: MerchBrain,
) -> MerchDraftOut:
    """Synchronous core: retrieve comparables, generate copy, price, persist a DRAFT.

    Identity/scope (``store_id``) is the caller's — never from the model. The brain only
    writes the copy; the price is computed structurally; nothing is published. This is what
    the async wrapper runs on a worker thread, and what tests call directly (key-free with a
    stub brain). Returns the persisted ``MerchDraftOut``.
    """
    comparables = find_comparables(session, brief=brief)
    comparable_lines = [
        f"{c.title} — {c.price_minor / 100:.2f} {c.slug}" for c in comparables
    ]
    listing = brain.draft(brief, comparable_lines)
    suggestion = suggest_price(comparables)
    return persist_draft(
        session, store_id=store_id, listing=listing, suggestion=suggestion
    )


def generate_merch_draft_async(
    factory: sessionmaker[Session],
    *,
    brief: str,
    store_id: str,
    brain: MerchBrain,
) -> Future[MerchDraftOut]:
    """Run draft generation OFF the request critical path on a fresh session.

    The node returns immediately; this commits the draft on its own session/thread so the
    draft is retrievable once ready (the story's async requirement). Returns the ``Future``
    so a test can await the result deterministically. A worker failure is logged and
    re-raised through the Future (never crashes the request).
    """

    def _run() -> MerchDraftOut:
        with factory() as worker_session:
            try:
                draft = generate_merch_draft(
                    worker_session, brief=brief, store_id=store_id, brain=brain
                )
                worker_session.commit()
                return draft
            except Exception:  # noqa: BLE001 - surface through the Future, log as signal
                worker_session.rollback()
                _log.exception("async merch draft generation failed")
                raise

    return _POOL.submit(_run)


# --------------------------------------------------------------------------- #
# Policy content-version snapshot (semantic-cache invalidation; ADR-0034 §2).   #
# --------------------------------------------------------------------------- #
def policy_content_version(session: Session, *, store_id: str | None) -> str:
    """A version snapshot of the in-scope ACTIVE policies (for policy-cache invalidation).

    Folds the max ``updated_at`` + the sum of ``version`` across the policies a support
    answer could ground on (the store's policies + platform policies, mirroring
    ``retrieve_policies``' scope). Any policy EDIT — a body change bumps ``updated_at``, a
    version bump bumps the sum — changes this string, so ``cache_lookup`` treats every cached
    answer in that scope as stale and re-grounds. Lives here next to merch only because both
    are Day-17 write-adjacent concerns; it is a pure read.
    """
    stmt = select(
        func.max(Policy.updated_at), func.coalesce(func.sum(Policy.version), 0)
    ).where(Policy.is_active.is_(True))
    if store_id is not None:
        stmt = stmt.where((Policy.store_id == store_id) | (Policy.store_id.is_(None)))
    else:
        stmt = stmt.where(Policy.store_id.is_(None))
    row = session.execute(stmt).first()
    if row is None:
        return ""
    max_updated, version_sum = row
    return f"{max_updated}|{version_sum}"


__all__ = [
    "find_comparables",
    "generate_merch_draft",
    "generate_merch_draft_async",
    "persist_draft",
    "policy_content_version",
    "suggest_price",
]
