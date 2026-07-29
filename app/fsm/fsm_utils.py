from .models import UserSession


def encode_session(session: UserSession) -> str:
    return session.model_dump_json()


def decode_session(data: str) -> UserSession:
    return UserSession.model_validate_json(data)
