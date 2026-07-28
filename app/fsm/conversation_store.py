import json

from pydantic import ValidationError
from redis.asyncio import Redis

from app.utils.types import SessionState, UserSession


class ConversationStore:
    PREFIX = "session"

    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    def _key(self, session_id: str) -> str:
        return f"{self.PREFIX}:{session_id}"

    async def get_session(self, session_id: str) -> UserSession | None:
        raw_redis_str = await self.redis.get(self._key(session_id))

        if not raw_redis_str:
            return None

        try:
            return UserSession.model_validate_json(raw_redis_str)
        except ValidationError:
            # TODO: Log error
            return None

    async def save_session(
        self,
        session_id: str,
        state: SessionState,
        ttl: int = 3600,
    ) -> None:
        await self.redis.set(
            self._key(session_id),
            json.dumps(state),
            ex=ttl,
        )

    async def delete_session(
        self,
        session_id: str,
    ) -> None:
        await self.redis.delete(self._key(session_id))
