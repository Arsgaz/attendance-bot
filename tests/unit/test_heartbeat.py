from pathlib import Path

import pytest

from observability.heartbeat import (
    StaleHeartbeatError,
    ensure_fresh_heartbeat,
    heartbeat_age,
    heartbeat_path,
    write_heartbeat,
)


def test_write_and_read_heartbeat(tmp_path: Path) -> None:
    path = heartbeat_path(tmp_path, "worker")

    write_heartbeat(path)

    assert path == tmp_path / "worker.heartbeat"
    assert heartbeat_age(path) >= 0
    assert ensure_fresh_heartbeat(path, max_age_seconds=10) >= 0


def test_missing_and_stale_heartbeat_are_rejected(tmp_path: Path) -> None:
    path = heartbeat_path(tmp_path, "backup")
    with pytest.raises(StaleHeartbeatError):
        ensure_fresh_heartbeat(path, max_age_seconds=10)

    path.write_text("100.0\n", encoding="utf-8")
    with pytest.raises(StaleHeartbeatError):
        ensure_fresh_heartbeat(path, max_age_seconds=1)
