from pathlib import Path

from redis.asyncio import Redis
from redis.commands.core import AsyncScript

LUA_SAVE_SESSION_SCRIPT = "update_session_state.lua"
_lua_update_session: AsyncScript | None = None


def register_session_update_script(redis_client: Redis) -> None:
    global _lua_update_session
    script_path = Path(__file__).with_name("lua") / LUA_SAVE_SESSION_SCRIPT
    lua_content = script_path.read_text()
    _lua_update_session = redis_client.register_script(lua_content)


def get_update_script() -> AsyncScript:
    if _lua_update_session is None:
        raise RuntimeError("Script not registered")
    return _lua_update_session
