from datetime import date


def attendance_week_title(week_start: date, week_end: date) -> str:
    return (
        f"Ваши отметки за {week_start:%d.%m.%Y}–{week_end:%d.%m.%Y}. "
        "Нажмите на запись, чтобы исправить или удалить её:"
    )


def attendance_dates_week_title(week_start: date, week_end: date) -> str:
    return f"Выберите дату. Неделя {week_start:%d.%m.%Y}–{week_end:%d.%m.%Y}:"
