from __future__ import annotations

from datetime import datetime, timezone

from app.fsm.models import FSMResult, SessionContext, SessionState, UserSession


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
