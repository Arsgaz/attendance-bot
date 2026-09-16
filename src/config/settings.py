from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: SecretStr = SecretStr("")
    database_url: str = "sqlite+aiosqlite:///./attendance.db"
    google_spreadsheet_id: str = ""
    google_sheet_name: str = "Журнал"
    google_settings_sheet_name: str = "Настройки"
    google_credentials_file: str = ""
    google_student_header_row: int = 3
    google_attendance_first_row: int = 4
    google_attendance_last_row: int = 340
    google_student_first_column: int = 6
    google_student_last_column: int = 28
    google_service_date_column: str = "AC"
    default_timezone: str = "Europe/Moscow"
    bonus_weekly_limit: int = 3
    admin_telegram_ids: list[int] = Field(default_factory=list)
    sync_queue_poll_interval_seconds: int = 5
    sync_queue_max_attempts: int = 10
    sync_queue_batch_size: int = 20
    sync_queue_lock_timeout_seconds: int = 300
    sync_queue_retry_base_seconds: int = 5
    sync_queue_retry_max_seconds: int = 900
    sheet_reconciliation_interval_seconds: int = 60
    backup_dir: str = "./backups"
    backup_interval_seconds: int = 86400
    backup_daily_retention: int = 7
    backup_weekly_retention: int = 4
    log_level: str = "INFO"
