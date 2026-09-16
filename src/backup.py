import argparse
import gzip
import os
import shutil
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from config.settings import Settings
from observability import configure_logging, get_logger

logger = get_logger(__name__)


def sqlite_path(database_url: str) -> Path:
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if database_url.startswith(prefix):
            return Path(database_url.removeprefix(prefix)).resolve()
    raise ValueError("backup supports only SQLite DATABASE_URL")


def verify_database(path: Path) -> None:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    finally:
        connection.close()
    if result != ("ok",):
        raise RuntimeError(f"SQLite integrity check failed: {result!r}")


def create_backup(
    database: Path,
    backup_dir: Path,
    *,
    now: datetime | None = None,
    label: str = "attendance",
) -> Path:
    if not database.is_file():
        raise FileNotFoundError(database)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = backup_dir / f"{label}-{timestamp}.sqlite3.gz"
    snapshot = backup_dir / f".{label}-{timestamp}.sqlite3.tmp"
    compressed = backup_dir / f".{label}-{timestamp}.sqlite3.gz.tmp"
    try:
        source_connection = sqlite3.connect(database)
        destination_connection = sqlite3.connect(snapshot)
        try:
            source_connection.backup(destination_connection)
        finally:
            destination_connection.close()
            source_connection.close()
        verify_database(snapshot)
        with snapshot.open("rb") as source, gzip.open(compressed, "wb") as destination:
            shutil.copyfileobj(source, destination)
        os.replace(compressed, target)
        return target
    finally:
        snapshot.unlink(missing_ok=True)
        compressed.unlink(missing_ok=True)


def rotate_backups(backup_dir: Path, *, daily: int, weekly: int) -> list[Path]:
    backups = sorted(backup_dir.glob("attendance-*.sqlite3.gz"), reverse=True)
    keep = set(backups[: max(daily, 0)])
    weekly_kept: set[tuple[int, int]] = set()
    for backup in backups:
        parsed = _backup_datetime(backup)
        if parsed is None:
            continue
        week = parsed.isocalendar()[:2]
        if week not in weekly_kept and len(weekly_kept) < max(weekly, 0):
            weekly_kept.add(week)
            keep.add(backup)
    removed: list[Path] = []
    for backup in backups:
        if backup not in keep:
            backup.unlink()
            removed.append(backup)
    return removed


def restore_backup(database: Path, archive: Path, backup_dir: Path) -> Path:
    if not archive.is_file():
        raise FileNotFoundError(archive)
    database.parent.mkdir(parents=True, exist_ok=True)
    restored = database.with_name(f".{database.name}.restore.tmp")
    restored.unlink(missing_ok=True)
    try:
        with gzip.open(archive, "rb") as source, restored.open("wb") as destination:
            shutil.copyfileobj(source, destination)
        verify_database(restored)
        emergency = create_backup(database, backup_dir, label="pre-restore")
        for suffix in ("-wal", "-shm"):
            Path(f"{database}{suffix}").unlink(missing_ok=True)
        os.replace(restored, database)
        verify_database(database)
        return emergency
    finally:
        restored.unlink(missing_ok=True)


def _backup_datetime(path: Path) -> datetime | None:
    timestamp = path.name.removeprefix("attendance-").removesuffix(".sqlite3.gz")
    try:
        return datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


def _create_and_rotate(settings: Settings) -> Path:
    database = sqlite_path(settings.database_url)
    backup_dir = Path(settings.backup_dir).resolve()
    result = create_backup(database, backup_dir)
    removed = rotate_backups(
        backup_dir,
        daily=settings.backup_daily_retention,
        weekly=settings.backup_weekly_retention,
    )
    logger.info("backup_created", archive=str(result), rotated=len(removed))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="SQLite backup and restore utility")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--loop", action="store_true", help="create backups periodically")
    mode.add_argument("--restore", type=Path, help="restore a .sqlite3.gz archive")
    parser.add_argument("--yes", action="store_true", help="confirm destructive restore")
    args = parser.parse_args()
    settings = Settings()  # type: ignore[call-arg]
    configure_logging(service="backup", level=settings.log_level)
    if args.restore is not None:
        if not args.yes:
            parser.error("--restore requires --yes; stop bot and worker before restoring")
        emergency = restore_backup(
            sqlite_path(settings.database_url),
            args.restore.resolve(),
            Path(settings.backup_dir).resolve(),
        )
        logger.warning(
            "database_restored",
            archive=str(args.restore.resolve()),
            previous_database_backup=str(emergency),
        )
        return
    while True:
        try:
            _create_and_rotate(settings)
        except Exception:
            logger.exception("backup_failed")
            if not args.loop:
                raise
        if not args.loop:
            return
        time.sleep(settings.backup_interval_seconds)


if __name__ == "__main__":
    main()
