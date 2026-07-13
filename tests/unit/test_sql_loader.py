from app.sql import loader as sql_loader


def test_load_sql_caches_file_contents(tmp_path):
    sql_root = tmp_path / "app" / "sql"
    sql_root.mkdir(parents=True)

    sql_file = sql_root / "sample.sql"
    sql_file.write_text("SELECT 1\n", encoding="utf-8")

    fake_loader_file = sql_root / "loader.py"
    fake_loader_file.write_text("", encoding="utf-8")

    original_loader_file = sql_loader.__file__
    sql_loader.load_sql.cache_clear()
    sql_loader.__file__ = str(fake_loader_file)

    try:
        first = sql_loader.load_sql("sample.sql")
        sql_file.write_text("SELECT 2\n", encoding="utf-8")
        second = sql_loader.load_sql("sample.sql")
    finally:
        sql_loader.__file__ = original_loader_file
        sql_loader.load_sql.cache_clear()

    assert first == "SELECT 1\n"
    assert second == "SELECT 1\n"
