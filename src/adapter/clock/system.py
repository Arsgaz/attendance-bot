from datetime import datetime
from zoneinfo import ZoneInfo


class SystemClock:
    def __init__(self, timezone: ZoneInfo) -> None:
        self._timezone = timezone

    def now(self) -> datetime:
        return datetime.now(tz=self._timezone)
