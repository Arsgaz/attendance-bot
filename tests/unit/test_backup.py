import gzip
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from backup import create_backup, restore_backup, rotate_backups, sqlite_path, verify_database


def _database(path: Path, value: str) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("create table if not exists example (value text not null)")
        connection.execute("delete from example")
        connection.execute("insert into example values (?)", (value,))
        connection.commit()
    finally:
        connection.close()


def _value(path: Path) -> str:
    connection = sqlite3.connect(path)
    try:
        return str(connection.execute("select value from example").fetchone()[0])
    finally:
        connection.close()


def test_create_and_restore_verified_sqlite_backup(tmp_path: Path) -> None:
    database = tmp_path / "attendance.db"
    backup_dir = tmp_path / "backups"
    _database(database, "before")

    archive = create_backup(
        database,
        backup_dir,
        now=datetime(2026, 9, 16, 12, tzinfo=UTC),
    )
    _database(database, "after")
    emergency = restore_backup(database, archive, backup_dir)

    assert archive.name == "attendance-20260916T120000Z.sqlite3.gz"
    assert emergency.name.startswith("pre-restore-")
    assert _value(database) == "before"
    verify_database(database)


def test_rotation_keeps_recent_daily_and_one_per_week(tmp_path: Path) -> None:
    database = tmp_path / "attendance.db"
    backup_dir = tmp_path / "backups"
    _database(database, "value")
    start = datetime(2026, 8, 1, tzinfo=UTC)
    for day in range(50):
        create_backup(database, backup_dir, now=start + timedelta(days=day))

    rotate_backups(backup_dir, daily=7, weekly=4)

    remaining = list(backup_dir.glob("attendance-*.sqlite3.gz"))
    assert 7 <= len(remaining) <= 11
    assert backup_dir / "attendance-20260919T000000Z.sqlite3.gz" in remaining


def test_sqlite_url_and_invalid_archive(tmp_path: Path) -> None:
    assert sqlite_path("sqlite+aiosqlite:////data/attendance.db") == Path(
        "/data/attendance.db",
    )
    invalid = tmp_path / "invalid.sqlite3.gz"
    with gzip.open(invalid, "wb") as stream:
        stream.write(b"not sqlite")
    database = tmp_path / "attendance.db"
    _database(database, "safe")

    try:
        restore_backup(database, invalid, tmp_path / "backups")
    except sqlite3.DatabaseError:
        pass
    else:
        raise AssertionError("invalid backup must not be restored")
    assert _value(database) == "safe"
