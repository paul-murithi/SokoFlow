"""add pg_trgm fuzzy search support

Revision ID: d248148b39c3
Revises: 8a9f1d7c7c4b
Create Date: 2026-08-06 15:55:20.713016

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd248148b39c3'
down_revision: Union[str, None] = '8a9f1d7c7c4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.create_index(
        "ix_products_name_lower_trgm",
        "products",
        ["name_lower"],
        postgresql_using="gin",
        postgresql_ops={
            "name_lower": "gin_trgm_ops"
        },
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    op.drop_index(
        "ix_products_name_lower_trgm",
        table_name="products"
    )
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    # ### end Alembic commands ###
