"""add missing business constraints

Revision ID: 8a9f1d7c7c4b
Revises: 17d2ea0a8ec1
Create Date: 2026-07-22 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8a9f1d7c7c4b"
down_revision: Union[str, None] = "17d2ea0a8ec1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_inventory_product_id", "inventory", ["product_id"]
    )
    op.create_check_constraint(
        "ck_inventory_quantity_nonnegative", "inventory", "quantity >= 0"
    )
    op.create_check_constraint(
        "ck_inventory_low_stock_threshold_bounds",
        "inventory",
        "low_stock_threshold >= 0 AND low_stock_threshold <= 1000",
    )
    op.create_check_constraint(
        "ck_products_price_nonnegative", "products", "price >= 0"
    )
    op.create_check_constraint(
        "ck_sales_quantity_positive", "sales", "quantity > 0"
    )


def downgrade() -> None:
    op.drop_constraint("ck_sales_quantity_positive", "sales", type_="check")
    op.drop_constraint("ck_products_price_nonnegative", "products", type_="check")
    op.drop_constraint(
        "ck_inventory_low_stock_threshold_bounds", "inventory", type_="check"
    )
    op.drop_constraint(
        "ck_inventory_quantity_nonnegative", "inventory", type_="check"
    )
    op.drop_constraint("uq_inventory_product_id", "inventory", type_="unique")
