"""validate supported shop locales

Revision ID: b54f7a1d8e21
Revises: a1b751383aa0
Create Date: 2026-09-12 20:10:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "b54f7a1d8e21"
down_revision: Union[str, None] = "d248148b39c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_shops_locale_supported", "shops", "locale IN ('en', 'sw')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_shops_locale_supported", "shops", type_="check")
