from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.ai.product_resolver import ProductResolver
from app.fsm.models import ProductResolutionStatus, ScoredProductMatch


@pytest.fixture
def mock_repo():
    return AsyncMock()


@pytest.fixture
def resolver(mock_repo):
    return ProductResolver(product_repo=mock_repo)


@pytest.mark.asyncio
async def test_resolve_product_empty_term(resolver):
    mock_db = AsyncMock()
    res = await resolver.resolve_product(shop_id=uuid4(), search_term="", db=mock_db)
    assert res.status == ProductResolutionStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_resolve_product_no_matches(resolver, mock_repo):
    mock_db = AsyncMock()
    mock_repo.get_products_by_fuzzy_name.return_value = []

    res = await resolver.resolve_product(shop_id=uuid4(), search_term="Unicorn Bread", db=mock_db)
    assert res.status == ProductResolutionStatus.NOT_FOUND


@pytest.mark.asyncio
async def test_resolve_product_exact_match(resolver, mock_repo):
    mock_db = AsyncMock()
    shop_id = uuid4()
    prod_id = uuid4()

    match = ScoredProductMatch(
        id=prod_id,
        shop_id=shop_id,
        name="Super Bread 400g",
        sku="BREAD-400",
        price=Decimal("60.00"),
        similarity_score=0.85,
    )
    mock_repo.get_products_by_fuzzy_name.return_value = [match]

    res = await resolver.resolve_product(shop_id=shop_id, search_term="Super Bread", db=mock_db)
    assert res.status == ProductResolutionStatus.EXACT_MATCH
    assert res.product.id == prod_id


@pytest.mark.asyncio
async def test_resolve_product_ambiguous_close_candidates(resolver, mock_repo):
    mock_db = AsyncMock()
    shop_id = uuid4()

    match1 = ScoredProductMatch(
        id=uuid4(),
        shop_id=shop_id,
        name="Super Bread 400g",
        sku="BREAD-400",
        price=Decimal("60.00"),
        similarity_score=0.80,
    )
    match2 = ScoredProductMatch(
        id=uuid4(),
        shop_id=shop_id,
        name="Super Bread 800g",
        sku="BREAD-800",
        price=Decimal("110.00"),
        similarity_score=0.78,  # Delta < 0.15 margin
    )
    mock_repo.get_products_by_fuzzy_name.return_value = [match1, match2]

    res = await resolver.resolve_product(shop_id=shop_id, search_term="Super Bread", db=mock_db)
    assert res.status == ProductResolutionStatus.AMBIGUOUS
    assert len(res.candidates) == 2
