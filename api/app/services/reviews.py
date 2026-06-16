"""Product reviews: list + create, with the product rating rollup (J-BUY-02).

Routers stay thin; review reads/writes + the rating-rollup recompute live here. The
``reviews`` table already exists (migration 0002, with a UNIQUE (product_id, user_id)
constraint and a 1..5 CHECK); ``products.rating_avg`` / ``rating_count`` are DERIVED
columns recomputed app-side on every write (see the model docstring).

Uniqueness: one review per (product, user). A second attempt -> ``409 duplicate_review``.
The rating rollup is recomputed from the live review set after each insert so list/detail
cards stay consistent — ``rating_avg`` rounds to one decimal (the column is Numeric(2,1)).
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.pagination import decode_cursor, encode_cursor
from app.core.errors import APIError
from app.db.models import Product
from app.db.models.catalog import Review
from app.schemas.catalog import ReviewCreate, ReviewOut
from app.schemas.enums import ProductStatus
from app.schemas.envelope import Envelope, ErrorCode, ListEnvelope, PageMeta

_ACTIVE = ProductStatus.active.value


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def _not_found(thing: str) -> APIError:
    return APIError(
        status_code=404,
        code=ErrorCode.not_found,
        message=f"We couldn't find that {thing}.",
    )


def _review_out(review: Review) -> ReviewOut:
    return ReviewOut(
        id=review.id,
        product_id=review.product_id,
        user_id=review.user_id,
        rating=review.rating,
        title=review.title,
        body=review.body,
        created_at=review.created_at,
    )


def _load_visible_product(session: Session, product_id: str) -> Product:
    """An active, non-deleted product or 404 (reviews attach to visible products only)."""
    if not _is_uuid(product_id):
        raise _not_found("product")
    product = session.scalars(
        select(Product).where(
            Product.id == product_id,
            Product.status == _ACTIVE,
            Product.deleted_at.is_(None),
        )
    ).first()
    if product is None:
        raise _not_found("product")
    return product


def _recompute_rollup(session: Session, product: Product) -> None:
    """Recompute ``products.rating_avg`` / ``rating_count`` from the live review set."""
    avg, count = session.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.product_id == product.id
        )
    ).one()
    product.rating_count = int(count)
    product.rating_avg = round(float(avg), 1) if count else None
    session.flush()


def list_reviews(
    session: Session,
    product_id: str,
    *,
    cursor: str | None,
    limit: int,
) -> ListEnvelope[ReviewOut]:
    """Reviews for a product, newest first, cursor-paginated (404 if product missing)."""
    _load_visible_product(session, product_id)

    stmt = (
        select(Review)
        .where(Review.product_id == product_id)
        .order_by(Review.created_at.desc(), Review.id.desc())
    )
    if cursor is not None:
        pos = decode_cursor(cursor)
        stmt = stmt.where(
            (Review.created_at < pos.created_at)
            | ((Review.created_at == pos.created_at) & (Review.id < pos.id))
        )

    rows = list(session.scalars(stmt.limit(limit + 1)))
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = (
        encode_cursor(page[-1].created_at, page[-1].id) if has_more and page else None
    )
    return ListEnvelope(
        data=[_review_out(r) for r in page],
        meta=PageMeta(next_cursor=next_cursor, limit=limit, total=None),
    )


def create_review(
    session: Session,
    user_id: str,
    product_id: str,
    body: ReviewCreate,
) -> Envelope[ReviewOut]:
    """Add a review (one per user/product); recompute the rating rollup.

    A second review by the same user on the same product -> ``409 duplicate_review``.
    """
    product = _load_visible_product(session, product_id)

    exists = session.scalars(
        select(Review.id).where(
            Review.product_id == product_id, Review.user_id == user_id
        )
    ).first()
    if exists is not None:
        raise APIError(
            status_code=409,
            code=ErrorCode.duplicate_review,
            message="You've already reviewed this product.",
        )

    review = Review(
        product_id=product_id,
        user_id=user_id,
        rating=body.rating,
        title=body.title,
        body=body.body,
    )
    session.add(review)
    session.flush()
    _recompute_rollup(session, product)
    session.refresh(review)
    return Envelope(data=_review_out(review))
