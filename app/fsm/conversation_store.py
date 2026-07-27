import json

from redis.asyncio import Redis

from app.utils.types import SessionState


class ConversationStore:
    PREFIX = "conversation"

    def __init__(self, redis: Redis[str]) -> None:
        self.redis = redis

    def _key(self, conversation_id: str) -> str:
        return f"{self.PREFIX}:{conversation_id}"

    async def get_session(self, conversation_id: str) -> None:
        value = await self.redis.get(self._key(conversation_id))

        if value is None:
            ...

    async def save_session(
        self,
        conversation_id: str,
        state: SessionState,
        ttl: int = 3600,
    ) -> None:
        await self.redis.set(
            self._key(conversation_id),
            json.dumps(state),
            ex=ttl,
        )

    async def delete_session(
        self,
        conversation_id: str,
    ) -> None:
        await self.redis.delete(self._key(conversation_id))
