"""Agent-backed seller merchandising NUDGES — surface + audited reversible accept (J-SEL-03/04).

A "nudge" is the SELLER-FACING surfacing of a grounded merchandising suggestion produced by
Echo's Day-17 merch agent (``app.agent.merch``). It is NOT a parallel brain: the grounding
core is reused verbatim —

  * ``find_comparables`` retrieves REAL same-domain catalog rows (the live retrieval seam),
    EXCLUDING the seller's own store so a nudge prices a product against the wider market;
  * ``suggest_price`` computes the comparables' MEDIAN lowest-active price, surfaced WITH its
    basis (the rows + the rule). No invented competitor/price data, ever.

A nudge fires for one of the seller's OWN active products when its current price is out of
line with that grounded median (a re-price suggestion). The ``suggested_change`` is a DRAFT
proposal; ``accept`` is the ONLY mutation.

PERSISTENCE MODEL (ADR-0035): nudges are generated ON THE FLY from the catalog — there is NO
``seller_nudges`` table. The ``nudge_id`` is the product id: a product has at most one live
nudge (its current price vs. the grounded median), so the id is stable and ``accept`` can
re-resolve + re-ground it deterministically. Reversibility rides entirely on the
``agent_actions`` audit row: accept records the PRIOR per-variant prices in the row's payload,
so an undo is a pure replay of that snapshot (no extra table needed — lighter, and the audit
trail is the single source of truth the Day-20 FE reads).

SCOPE + GUARDRAILS: identity/scope come from ``require_user`` (the caller's OWN store), never
from model output; a foreign/unknown product 404s with no existence leak. The only
seller-supplied free field is the optional ``idempotency_key`` — it is scanned for injection
before use. Accept is idempotent via ``app.services.idempotency``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.guardrails import scan_for_injection
from app.agent.merch import find_comparables, suggest_price
from app.api.pagination import decode_cursor, encode_cursor
from app.core.errors import APIError
from app.db.models import AgentAction, Product, Store, Variant
from app.schemas.agent import PriceSuggestionOut
from app.schemas.enums import AgentOutcome, ProductStatus
from app.schemas.envelope import Envelope, ErrorCode, ListEnvelope, PageMeta
from app.schemas.seller import NudgeAcceptRequest, NudgeOut

# A nudge only fires when the grounded median differs from the product's current price by at
# least this fraction — a tiny gap is noise, not a merchandising signal worth surfacing.
_MATERIAL_DELTA = 0.05

# The audit action_type for an accepted nudge. The reversible PRIOR state lives in its payload.
_ACCEPT_ACTION = "merch_nudge_accept"


def _not_found(thing: str) -> APIError:
    return APIError(
        status_code=404,
        code=ErrorCode.not_found,
        message=f"We couldn't find that {thing}.",
    )


def _load_own_store(session: Session, user_id: str) -> Store:
    """The caller's store, or 404 (a seller must onboard before any nudge op)."""
    store = session.scalars(select(Store).where(Store.owner_id == user_id)).first()
    if store is None:
        raise _not_found("store")
    return store


def _active_variants(session: Session, product_id: str) -> list[Variant]:
    """The product's ACTIVE variants (the rows a re-price nudge would touch), id-ordered."""
    return list(
        session.scalars(
            select(Variant)
            .where(Variant.product_id == product_id, Variant.is_active.is_(True))
            .order_by(Variant.id)
        )
    )


def _current_price(variants: list[Variant]) -> int | None:
    """The product's current headline price = its cheapest active variant (minor units)."""
    prices = [v.price_minor for v in variants]
    return min(prices) if prices else None


def _ground_nudge(
    session: Session, *, product: Product, store_id: str
) -> tuple[NudgeOut, PriceSuggestionOut] | None:
    """Build a grounded re-price nudge for one of the seller's products, or None.

    Reuses the merch agent's grounding core: comparables (EXCLUDING the seller's own store)
    + the median price suggestion with its basis. Returns ``None`` when there is no current
    price, no comparable basis, or the gap to the grounded median is immaterial — i.e. there
    is nothing honest to nudge about. The ``reason`` references the real comparable rows; no
    competitor/price data is invented.
    """
    variants = _active_variants(session, product.id)
    current = _current_price(variants)
    if current is None or current <= 0:
        return None

    comparables = find_comparables(
        session, brief=_brief_for(product), exclude_store_id=store_id
    )
    suggestion = suggest_price(comparables)
    target = suggestion.suggested_price_minor
    if target is None or not comparables:
        return None
    if abs(target - current) < current * _MATERIAL_DELTA:
        return None  # current price already tracks the market — no nudge

    gerund = "raising" if target > current else "lowering"
    headline = (
        f"Consider {gerund} the price of "
        f"{product.title!r} to {target / 100:.2f} {suggestion.currency}"
    )
    basis_lower = suggestion.basis[0].lower() + suggestion.basis[1:]
    reason = (
        f"Its current price is {current / 100:.2f} {suggestion.currency}, while the "
        f"{basis_lower} This suggests {gerund} toward the market median."
    )
    nudge = NudgeOut(
        id=product.id,
        product_id=product.id,
        headline=headline,
        reason=reason,
        suggested_change={
            "kind": "reprice",
            "current_price_minor": current,
            "suggested_price_minor": target,
            "currency": suggestion.currency,
            "comparable_count": len(comparables),
        },
    )
    return nudge, suggestion


def _brief_for(product: Product) -> str:
    """A retrieval brief for the comparables search — the product's own salient copy.

    Grounded purely in the seller's existing listing (title + category); never seller free
    text at nudge time, so there is nothing untrusted to re-instruct the retrieval.
    """
    parts = [product.title]
    if product.category:
        parts.append(product.category)
    return " ".join(parts)


# --------------------------------------------------------------------------- #
# GET /seller/nudges — grounded re-price nudges for the seller's OWN catalog.   #
# --------------------------------------------------------------------------- #
def list_nudges(
    session: Session,
    user_id: str,
    *,
    cursor: str | None,
    limit: int,
) -> ListEnvelope[NudgeOut]:
    """List grounded merchandising nudges for the caller's OWN active products.

    Scoped to the seller's store (``stores.owner_id == user_id``); a seller never sees a
    nudge for another store's product. Products are walked newest-first (cursor-paginated on
    ``created_at, id``); each yields at most one re-price nudge when its price is materially
    off the grounded comparables median. The cursor advances over PRODUCTS scanned (stable
    paging) — a page may surface fewer nudges than the limit when some products have nothing
    to nudge, with ``next_cursor`` set whenever more products remain to scan.
    """
    store = _load_own_store(session, user_id)

    stmt = (
        select(Product)
        .where(
            Product.store_id == store.id,
            Product.status == ProductStatus.active.value,
            Product.deleted_at.is_(None),
        )
        .order_by(Product.created_at.desc(), Product.id.desc())
    )
    if cursor is not None:
        pos = decode_cursor(cursor)
        stmt = stmt.where(
            (Product.created_at < pos.created_at)
            | ((Product.created_at == pos.created_at) & (Product.id < pos.id))
        )

    nudges: list[NudgeOut] = []
    last: Product | None = None
    next_cursor: str | None = None
    # Walk products until we've filled the page of NUDGES, requesting one product at a time
    # past the page so we learn whether more remain without a second query.
    for product in session.scalars(stmt):
        if len(nudges) >= limit:
            # There is at least one more product to scan -> a next page exists.
            next_cursor = (
                encode_cursor(last.created_at, last.id) if last is not None else None
            )
            break
        grounded = _ground_nudge(session, product=product, store_id=store.id)
        if grounded is not None:
            nudges.append(grounded[0])
            last = product

    return ListEnvelope(
        data=nudges,
        meta=PageMeta(next_cursor=next_cursor, limit=limit, total=None),
    )


# --------------------------------------------------------------------------- #
# POST /seller/nudges/{nudge_id}/accept — apply the nudge (audited, reversible).#
# --------------------------------------------------------------------------- #
def accept_nudge(
    session: Session,
    user_id: str,
    nudge_id: str,
    body: NudgeAcceptRequest,
) -> Envelope[NudgeOut]:
    """Apply a re-price nudge to the seller's OWN product — audited + reversible + idempotent.

    ``nudge_id`` is the product id. The nudge is RE-GROUNDED at accept time (never trusting a
    stale client-side suggestion): comparables + the median are recomputed, and only that
    fresh suggested price is applied — so an accept can't be tricked into an arbitrary price.
    Scope: a foreign/unknown product 404s (no existence leak). A product whose price no
    longer warrants a nudge (the market moved) 404s as "nudge" — there is nothing to apply.

    REVERSIBILITY: before mutating, the PRIOR per-variant prices are snapshotted into the
    ``agent_actions`` audit row's payload (``action_type='merch_nudge_accept'``,
    outcome=applied). An undo is a replay of that snapshot — no separate table is needed.

    IDEMPOTENCY: keyed on the optional ``idempotency_key`` via ``app.services.idempotency``;
    a replay re-emits the stored ``NudgeOut`` without re-applying the price. The key is the
    only seller-supplied free field, so it is scanned for injection before use.
    """
    store = _load_own_store(session, user_id)

    # Guardrail: the one untrusted seller-supplied field. A crafted key is refused + logged.
    key = body.idempotency_key
    if key:
        hit = scan_for_injection(key)
        if hit is not None:
            session.add(
                AgentAction(
                    conversation_id=None,
                    actor_user_id=user_id,
                    action_type="guardrail",
                    payload={
                        "kind": hit.kind.value,
                        "span": hit.span,
                        "reason": "prompt_injection",
                        "field": "idempotency_key",
                    },
                    outcome=AgentOutcome.refused.value,
                )
            )
            session.flush()
            raise APIError(
                status_code=422,
                code=ErrorCode.validation_error,
                message="That idempotency key wasn't accepted.",
            )

    endpoint = f"seller:nudge_accept:{nudge_id}"
    from app.services import idempotency as idempotency_service

    replay = idempotency_service.lookup(session, user_id, key, endpoint)
    if replay is not None:
        return Envelope(data=NudgeOut.model_validate(replay.body))

    product = (
        session.get(Product, nudge_id)
        if _looks_like_uuid(nudge_id)
        else None
    )
    # No-leak: a foreign product, an unknown id, or a non-active product all 404 the same.
    if (
        product is None
        or product.store_id != store.id
        or product.status != ProductStatus.active.value
        or product.deleted_at is not None
    ):
        raise _not_found("nudge")

    grounded = _ground_nudge(session, product=product, store_id=store.id)
    if grounded is None:
        # The market moved — there is no longer a grounded nudge to apply here.
        raise _not_found("nudge")
    nudge, suggestion = grounded
    target = suggestion.suggested_price_minor
    assert target is not None  # _ground_nudge guarantees a price when it returns a nudge

    variants = _active_variants(session, product.id)
    prior_prices = {v.id: v.price_minor for v in variants}

    # Reversible audit row FIRST — capture the prior state before any mutation, so even a
    # mid-mutation failure leaves an honest "what it was" record to reverse from.
    session.add(
        AgentAction(
            conversation_id=None,
            actor_user_id=user_id,
            action_type=_ACCEPT_ACTION,
            payload={
                "nudge_id": nudge_id,
                "product_id": product.id,
                "suggested_change": nudge.suggested_change,
                "applied_price_minor": target,
                "prior_variant_prices": prior_prices,
                "basis": suggestion.basis,
                "reversible": True,
            },
            outcome=AgentOutcome.applied.value,
        )
    )

    # Apply: move every active variant to the grounded median price.
    for variant in variants:
        variant.price_minor = target
    session.flush()

    idempotency_service.store(
        session, user_id, key, endpoint, status_code=200, body=nudge
    )
    return Envelope(data=nudge)


def _looks_like_uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


__all__ = ["accept_nudge", "list_nudges"]
