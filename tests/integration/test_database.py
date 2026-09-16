from pathlib import Path

from sqlalchemy import text

from adapter.database.engine import create_engine


async def test_sqlite_engine_enables_required_pragmas(tmp_path: Path) -> None:
    database_path = tmp_path / "database.sqlite3"
    engine = create_engine(f"sqlite+aiosqlite:///{database_path}")

    try:
        async with engine.connect() as connection:
            foreign_keys = (await connection.execute(text("PRAGMA foreign_keys"))).scalar_one()
            journal_mode = (await connection.execute(text("PRAGMA journal_mode"))).scalar_one()
            busy_timeout = (await connection.execute(text("PRAGMA busy_timeout"))).scalar_one()
    finally:
        await engine.dispose()

    assert foreign_keys == 1
    assert journal_mode == "wal"
    assert busy_timeout == 5000
