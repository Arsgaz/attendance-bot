import os
import time
from pathlib import Path


class StaleHeartbeatError(RuntimeError):
    pass


def heartbeat_path(directory: str | Path, service: str) -> Path:
    return Path(directory) / f"{service}.heartbeat"


def write_heartbeat(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".heartbeat.tmp")
    temporary.write_text(f"{time.time():.6f}\n", encoding="utf-8")
    os.replace(temporary, path)


def heartbeat_age(path: Path, *, now: float | None = None) -> float:
    try:
        value = float(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError) as error:
        raise StaleHeartbeatError(f"heartbeat is missing or invalid: {path}") from error
    return max(0.0, (time.time() if now is None else now) - value)


def ensure_fresh_heartbeat(path: Path, *, max_age_seconds: float) -> float:
    age = heartbeat_age(path)
    if age > max_age_seconds:
        raise StaleHeartbeatError(
            f"heartbeat is stale: {path}; age={age:.1f}s; max={max_age_seconds:.1f}s",
        )
    return age
