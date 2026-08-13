from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_worker_db
from app.fsm.models import FSMResult, ScoredProductMatch, SessionContext, SessionState, UserSession
from app.models import Shop
from app.utils.errors import InvalidInputError


class FSMPrimitives:
    def _transition(self, session: UserSession, new_state: SessionState) -> None:
        if session.state != new_state:
            session.context.history.append(session.state)
            session.state = new_state
        session.context.last_activity = datetime.now(timezone.utc)

    def _clear_context_preserving_history(self, session: UserSession) -> None:
        history = list(session.context.history)
        session.context = SessionContext(
            shop_id=session.context.shop_id,
            history=history,
            last_activity=datetime.now(timezone.utc),
        )

    def _build_result(
        self,
        *,
        previous_state: SessionState,
        session: UserSession,
        reply_text: str,
    ) -> FSMResult:
        return FSMResult(
            previous_state=previous_state,
            new_state=session.state,
            context=session.context.model_copy(deep=True),
            reply_text=reply_text,
        )

    def _resolve_product_choice(self, session: UserSession, message: str) -> ScoredProductMatch:
        try:
            choice = int(message.strip())
        except (ValueError, TypeError):
            raise InvalidInputError("Choice must be a number")

        candidates = session.context.product_candidates

        if choice < 1 or choice > len(candidates):
            raise InvalidInputError("Invalid Choice")

        selected_product = candidates[choice - 1]
        return selected_product

    def _format_product_choices(
        self,
        candidates: list[ScoredProductMatch],
    ) -> str:
        lines = [
            "Which product did you mean?",
            "",
        ]

        for index, product in enumerate(candidates, start=1):
            lines.append(f"{index}. {product.name} — {product.price}")

        lines.extend(["", f"Reply with a number from 1 to {len(candidates)}."])

        return "\n".join(lines)

    async def get_shop_id(self, db: AsyncSession, sender: str) -> UUID:
        stmt = select(Shop).where(Shop.phone == sender)
        result = await db.execute(stmt)
        shop = result.scalar_one_or_none()

        if shop is None:
            raise InvalidInputError("I couldn't find your shop profile. Please contact support.")

        return shop.id

    @asynccontextmanager  # pyright: ignore[reportDeprecated]
    async def _get_db_session(
        self, db_session: AsyncSession | None = None
    ) -> AsyncIterator[AsyncSession]:
        if db_session is not None:
            yield db_session
            return

        async with get_worker_db() as db_session:
            yield db_session
