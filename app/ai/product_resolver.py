import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.fsm.models import ProductResolution, ProductResolutionStatus, ScoredProductMatch
from app.repositories.product_repo import ProductRepository

logger = logging.getLogger(__name__)


class ProductResolver:
    """Resolves merchant product wording to concrete shop products using fuzzy matching

    and explicit confidence thresholds.
    """

    CONFIDENCE_DELTA_MARGIN: float = 0.15

    def __init__(self, product_repo: ProductRepository | None = None) -> None:
        self.product_repo = product_repo or ProductRepository()

    async def resolve_product(
        self,
        *,
        shop_id: UUID,
        search_term: str,
        db: AsyncSession,
        limit: int = 5,
    ) -> ProductResolution:
        """Resolves search_term to a ProductResolution status (EXACT_MATCH, AMBIGUOUS, NOT_FOUND).

        Does not guess when candidates are ambiguous or confidence is low.
        """
        cleaned_term = search_term.strip()
        if not cleaned_term:
            return ProductResolution(status=ProductResolutionStatus.NOT_FOUND)

        matches: list[ScoredProductMatch] = await self.product_repo.get_products_by_fuzzy_name(
            shop_id=shop_id,
            db=db,
            query=cleaned_term,
            limit=limit,
        )

        if not matches:
            logger.info("Product resolution found 0 candidates for term '%s'", cleaned_term)
            return ProductResolution(status=ProductResolutionStatus.NOT_FOUND)

        top_match = matches[0]
        confident_threshold = settings.confident_match_threshold

        # If top match reaches confident threshold
        if top_match.similarity_score >= confident_threshold:
            # If single candidate OR top candidate outscores second candidate
            if len(matches) == 1 or (
                top_match.similarity_score - matches[1].similarity_score
                >= self.CONFIDENCE_DELTA_MARGIN
            ):
                logger.info(
                    "Product resolution EXACT_MATCH for '%s' -> %s (score=%.2f)",
                    cleaned_term,
                    top_match.name,
                    top_match.similarity_score,
                )
                return ProductResolution(
                    status=ProductResolutionStatus.EXACT_MATCH,
                    product=top_match,
                    candidates=[top_match],
                )

        # Multiple plausible candidates or below confident margin -> Ambiguous
        logger.info(
            "Product resolution AMBIGUOUS for '%s' (%d candidates)", cleaned_term, len(matches)
        )
        return ProductResolution(
            status=ProductResolutionStatus.AMBIGUOUS,
            candidates=matches,
        )
