import asyncio
from pathlib import Path
from typing import Any, Protocol

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


class SheetsValuesClient(Protocol):
    async def batch_get(self, *, ranges: list[str]) -> list[list[list[object]]]: ...

    async def update(self, *, cell_range: str, value: str) -> None: ...


class GoogleApiSheetsValuesClient:
    _SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)

    def __init__(self, *, spreadsheet_id: str, service: Any) -> None:
        self._spreadsheet_id = spreadsheet_id
        self._values = service.spreadsheets().values()

    @classmethod
    def from_service_account_file(
        cls,
        *,
        spreadsheet_id: str,
        credentials_file: str | Path,
    ) -> "GoogleApiSheetsValuesClient":
        credentials = Credentials.from_service_account_file(
            str(credentials_file),
            scopes=cls._SCOPES,
        )
        service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        return cls(spreadsheet_id=spreadsheet_id, service=service)

    async def batch_get(self, *, ranges: list[str]) -> list[list[list[object]]]:
        def execute() -> dict[str, object]:
            return self._values.batchGet(
                spreadsheetId=self._spreadsheet_id,
                ranges=ranges,
                majorDimension="ROWS",
                valueRenderOption="UNFORMATTED_VALUE",
                dateTimeRenderOption="SERIAL_NUMBER",
            ).execute()

        response = await asyncio.to_thread(execute)
        value_ranges = response.get("valueRanges", [])
        return [item.get("values", []) for item in value_ranges]  # type: ignore[union-attr]

    async def update(self, *, cell_range: str, value: str) -> None:
        def execute() -> None:
            self._values.update(
                spreadsheetId=self._spreadsheet_id,
                range=cell_range,
                valueInputOption="RAW",
                body={"values": [[value]]},
            ).execute()

        await asyncio.to_thread(execute)
