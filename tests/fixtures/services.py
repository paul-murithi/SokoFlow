import pytest

from app.fsm.conversation_store import ConversationStore


@pytest.fixture
def store(redis_mock):  # pyright: ignore[]
    return ConversationStore(redis=redis_mock)
