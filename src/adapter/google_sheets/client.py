import asyncio
from pathlib import Path
from typing import Any, Protocol

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


class SheetsValuesClient(Protocol):
    async def batch_get(self, *, ranges: list[str]) -> list[list[list[object]]]: ...

    async def get_background_colors(
        self,
        *,
        cell_range: str,
    ) -> list[tuple[float, float, float] | None]: ...

    async def update(self, *, cell_range: str, value: str) -> None: ...


class GoogleApiSheetsValuesClient:
    _SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)

    def __init__(self, *, spreadsheet_id: str, service: Any) -> None:
        self._spreadsheet_id = spreadsheet_id
        self._spreadsheets = service.spreadsheets()
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

    async def get_background_colors(
        self,
        *,
        cell_range: str,
    ) -> list[tuple[float, float, float] | None]:
        def execute() -> dict[str, object]:
            return self._spreadsheets.get(
                spreadsheetId=self._spreadsheet_id,
                ranges=[cell_range],
                includeGridData=True,
                fields=(
                    "sheets(data(rowData(values(effectiveFormat(backgroundColor)))))"
                ),
            ).execute()

        response = await asyncio.to_thread(execute)
        sheets = response.get("sheets", [])
        if not sheets:
            return []
        data = sheets[0].get("data", [])  # type: ignore[union-attr]
        if not data:
            return []
        rows = data[0].get("rowData", [])
        colors: list[tuple[float, float, float] | None] = []
        for row in rows:
            values = row.get("values", [])
            color = (
                values[0].get("effectiveFormat", {}).get("backgroundColor", {})
                if values
                else {}
            )
            if not color:
                colors.append(None)
                continue
            colors.append(
                (
                    float(color.get("red", 0.0)),
                    float(color.get("green", 0.0)),
                    float(color.get("blue", 0.0)),
                ),
            )
        return colors

    async def update(self, *, cell_range: str, value: str) -> None:
        def execute() -> None:
            self._values.update(
                spreadsheetId=self._spreadsheet_id,
                range=cell_range,
                valueInputOption="RAW",
                body={"values": [[value]]},
            ).execute()

        await asyncio.to_thread(execute)
