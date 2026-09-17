import argparse
import asyncio
import json
import sys
from collections.abc import Sequence

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from adapter.database.engine import create_engine
from config.settings import Settings
from observability.heartbeat import ensure_fresh_heartbeat, heartbeat_path

HEARTBEAT_SERVICES = {"worker", "backup"}
SERVICES = ("telegram-bot", "vk-bot", "worker", "backup")


async def check_database(settings: Settings) -> str:
    engine = create_engine(settings.database_url)
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
            revision = await connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        await engine.dispose()
    expected = ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    if not revision or revision != expected:
        raise RuntimeError(f"database revision mismatch: current={revision!r}, expected={expected!r}")
    return str(revision)


def heartbeat_max_age(settings: Settings, service: str) -> float:
    if service == "worker":
        return max(30.0, settings.sync_queue_poll_interval_seconds * 3.0)
    if service == "backup":
        return settings.backup_interval_seconds + max(
            300.0,
            settings.backup_interval_seconds * 0.1,
        )
    raise ValueError(f"heartbeat is not configured for service: {service}")


async def check_service(service: str, settings: Settings) -> dict[str, object]:
    revision = await check_database(settings)
    result: dict[str, object] = {
        "status": "ok",
        "service": service,
        "database_revision": revision,
    }
    if service in HEARTBEAT_SERVICES:
        age = ensure_fresh_heartbeat(
            heartbeat_path(settings.healthcheck_heartbeat_dir, service),
            max_age_seconds=heartbeat_max_age(settings, service),
        )
        result["heartbeat_age_seconds"] = round(age, 3)
    return result


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Attendance Bot container healthcheck")
    parser.add_argument("--service", choices=SERVICES, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    settings = Settings()  # type: ignore[call-arg]
    try:
        result = asyncio.run(check_service(args.service, settings))
    except Exception as error:
        print(json.dumps({"status": "error", "service": args.service, "error": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
