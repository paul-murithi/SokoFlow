from typing import cast

from pydantic import ValidationError
from redis.asyncio import Redis
from typing_extensions import assert_never

from app.fsm.models import SessionState, UpdateSessionResult, UserSession
from app.utils.errors import CorruptedSessionError, SessionStateMismatchError

from .fsm_utils import decode_session, encode_session
from .session_lua import get_update_script


class ConversationStore:
    PREFIX = "session"

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    def _key(self, session_id: str) -> str:
        return f"{self.PREFIX}:{session_id}"

    def _dedup_key(self, message_id: str) -> str:
        return f"dedup:{message_id}"

    async def is_duplicate(self, message_id: str, ttl: int = 60) -> bool:
        redis_key = self._dedup_key(message_id)
        created = await self.redis.set(
            redis_key,
            "1",
            nx=True,
            ex=ttl,
        )
        return not bool(created)

    async def get_session(self, session_id: str) -> UserSession | None:
        raw_redis_str = await self.redis.get(self._key(session_id))

        if not raw_redis_str:
            return None

        try:
            return decode_session(raw_redis_str)
        except ValidationError:
            # TODO: Log error
            return None

    async def save_session(
        self,
        session_id: str,
        new_session: UserSession,
        old_session: UserSession | None = None,
        ttl: int = 3600,
    ) -> None:
        script = get_update_script()
        redis_key = self._key(session_id)
        expected_state = old_session.state if old_session else SessionState.IDLE

        raw_result = await script(
            keys=[redis_key], args=[expected_state, encode_session(new_session), ttl]
        )

        try:
            result = UpdateSessionResult(raw_result)
            self._handle_lua_result(result, session_id)
        except ValueError:
            raise RuntimeError(f"Invalid or unmapped Lua response {raw_result!r}")

    def _handle_lua_result(self, result: UpdateSessionResult, session_id: str) -> None:
        match result:
            case UpdateSessionResult.SUCCESS:
                return
            case UpdateSessionResult.STATE_MISMATCH:
                raise SessionStateMismatchError(session_id)
            case UpdateSessionResult.CORRUPTED_DATA:
                raise CorruptedSessionError(session_id)
            case _:
                assert_never(result)

    async def delete_session(
        self,
        session_id: str,
    ) -> bool:
        deleted = cast(int, await self.redis.delete(self._key(session_id)))
        return deleted == 1
