from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=None)
def load_sql(relative_path: str) -> str:
    return (Path(__file__).resolve().parent / relative_path).read_text()
