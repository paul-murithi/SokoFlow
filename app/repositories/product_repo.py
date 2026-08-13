from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.fsm.models import ScoredProductMatch
from app.models.product import Product
from app.sql import load_sql
from app.sql.queries import ProductSQL


class ProductRepository:
    async def list_products(self, shop_id: UUID, db: AsyncSession) -> list[Product]:
        stmt = select(Product).from_statement(text(load_sql(ProductSQL.LIST_BY_SHOP)))
        result = await db.scalars(stmt, {"shop_id": shop_id})
        return list(result.all())

    async def get_products_by_fuzzy_name(
        self,
        *,
        shop_id: UUID,
        db: AsyncSession,
        query: str,
        limit: int,
    ) -> list[ScoredProductMatch]:
        """returns candidates whose similarity is at least PRODUCT_MATCH_THRESHOLD,
        ordered by similarity descending.
        """
        query = query.strip().lower()

        stmt = text(load_sql(ProductSQL.GET_BY_FUZZY_SEARCH))

        result = await db.execute(
            stmt,
            {
                "shop_id": shop_id,
                "search_term": query,
                "min_threshold": settings.product_match_threshold,
                "limit": limit,
            },
        )

        return [ScoredProductMatch.model_validate(dict(row)) for row in result.mappings()]
