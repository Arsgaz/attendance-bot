# Документация Attendance Bot

Связанные эксплуатационные документы:

- [политика обработки персональных данных](./PRIVACY_POLICY.md);
- [политика безопасности и секретов](./SECURITY.md).

## 1. Назначение

Attendance Bot — сервис учёта посещаемости учебной группы. Google Sheets
является итоговым источником данных расписания, состава группы и посещаемости.
База данных хранит локальную проекцию, регистрации, аудит и очередь доставки.

Сервис позволяет:

- импортировать студентов и занятия из Google Sheets;
- привязывать внешний аккаунт к студенту;
- сохранять отметки `+`, `Н`, `Б`, `У`;
- вести историю изменений;
- асинхронно записывать итоговый статус в Google Sheets;
- повторять синхронизацию после временных ошибок;
- подключать Telegram- и VK-клиенты к общей бизнес-логике.

## 2. Основные бизнес-правила

- Один студент может иметь только одну активную внешнюю привязку.
- Одна пара `provider + external_user_id` может быть связана только с одним
  студентом.
- Регистрация активируется сразу после выбора студентом своего ФИО.
- Староста может отвязать внешний аккаунт без удаления студента, посещаемости и
  истории.
- Для сочетания `student_id + lesson_id` существует одна актуальная отметка.
- Студент может исправить или удалить собственную отметку без временного
  ограничения; каждое действие сохраняется в аудите и синхронизируется.
- Староста сможет исправлять чужие отметки с обязательным сохранением аудита.
- Временных ограничений на постановку отметки нет.
- `Б` требует предварительного согласования и ограничивается недельным лимитом.
- Внутренний статус `present` записывается в таблицу символом `✓`.
- Явные ручные значения посещаемости в Google Sheets приоритетнее локальной
  проекции после завершения исходящей синхронизации.

## 3. Архитектура

Проект организован как модульный монолит с DDD-слоями и разделением application
use cases на commands и queries.

```text
Telegram / VK / CLI / worker
              │
              ▼
        presentation
              │
              ▼
         application
 commands / queries / services
              │
              ▼
            domain
              ▲
              │
            ports
              ▲
              │
           adapters
   SQLAlchemy / Google Sheets
```

Направление зависимостей направлено внутрь: domain не зависит от SQLAlchemy,
aiogram или Google API.

### 3.1. Domain

`src/domain` содержит:

- `Student` — участник группы и роль старосты;
- `Lesson` — занятие, дата, предмет и подгруппа;
- `Attendance` — актуальная отметка и доменные события её изменения;
- `Registration` — активная или отвязанная внешняя учётная запись;
- `Actor` — универсальный автор действия;
- `AttendanceStatus` — внутренние статусы и отображаемые символы;
- policies недельного лимита `Б`.

### 3.2. Application

Commands изменяют состояние:

- `RegisterStudentHandler`;
- `UnlinkRegistrationHandler`;
- `MarkAttendanceHandler`;
- `UpdateOwnAttendanceHandler`;
- `CreateAttendanceRequestHandler`;
- `DecideAttendanceRequestHandler`;
- `ImportSheetStructureHandler`;
- `ReconcileSheetAttendanceHandler`;
- `SheetSyncTaskHandler`.

Каждый use case реализует типизированный контракт
`Interactor[InputDTO, OutputDTO]` из `application/base_interactor.py`. На границе
presentation формируется один command/query DTO, после чего выполняется единый
вызов `await interactor(dto)`. Репозитории и специальные методы обработчиков из
presentation напрямую не вызываются.

Сборка зависимостей разделена так же, как в референсных сервисах:

- `ApplicationProvider` создаёт application-scoped настройки и технические зависимости;
- `RepositoryProvider` связывает порты с SQLAlchemy-адаптерами в request scope;
- `InteractorProvider` отдельно собирает application handlers из портов и политик;
- presentation получает готовый interactor через `FromDishka[ConcreteHandler]`.

Presentation импортирует тип конкретного handler и его input DTO напрямую из
application — это ожидаемая внутренняя зависимость. Создание handler и знание о
его репозиториях остаются только в DI composition root.

Queries читают состояние:

- `GetMyRegistrationHandler`;
- `ListAvailableStudentsHandler`;
- `ListAttendanceDatesHandler` и `ListLessonsForDateHandler`;
- `ListMyAttendanceHandler`;
- `GetBonusBalanceHandler`;
- `ListPendingAttendanceRequestsHandler`;
- `ListStarostaExternalIdsHandler`.

Долгоживущие координаторы нескольких use case находятся в
`application/service`. Общие чистые application-политики, например расчёт
границ учебной недели, находятся в `application/common`. Application-слой не
импортирует `adapter`, `presentation`, `di` или `config`; это правило закреплено
архитектурными тестами.

Транзакционная граница задаётся через `UnitOfWork`. Изменение посещаемости,
история и задача синхронизации сохраняются одной транзакцией.

### 3.3. Ports

`src/port` содержит интерфейсы:

- репозиториев;
- Unit of Work;
- часов и генератора ID;
- Google Sheets gateway;
- источника и хранилища структуры таблицы.

### 3.4. Adapters

`src/adapter` содержит реализации портов:

- асинхронные SQLAlchemy-репозитории;
- ORM-модели и converters;
- SQLite/PostgreSQL-совместимую очередь синхронизации;
- Google Sheets API client;
- безопасный gateway записи одной ячейки;
- импорт структуры листов;
- системные часы и UUID-генератор.

### 3.5. Presentation

`src/presentation/telegram` содержит фабрику `Dispatcher`, routers, типизированные
callback DTO и keyboards. Presentation организован по пользовательским сценариям:

- `routers/start.py` — регистрация;
- `routers/attendance/marking.py` — выбор занятия и постановка отметки или заявки;
- `routers/attendance/history.py` — просмотр и изменение собственных отметок;
- `routers/attendance/navigation.py` — переходы между неделями и возврат в меню;
- `routers/starosta.py` — заявки и управление привязками;
- `keyboards/` — отдельные фабрики клавиатур регистрации, посещаемости и старосты;
- `routers/attendance/support.py` — presentation-only форматирование заголовков и
  отправка уже подготовленных уведомлений; application interactors из support-модулей
  не вызываются.

Пакет `routers/attendance` собирает feature-router’ы в своём `__init__.py`, поэтому `dispatcher`
не зависит от их внутренней структуры. Реализованы `/start`, выбор свободного студента,
подтверждение немедленной регистрации и переход в главное меню. Пункты меню
посещаемости позволяют выбрать доступную дату, предмет и статус, подтвердить
неизменяемую студентом отметку и сохранить её вместе с аудитом и задачей
синхронизации. На промежуточных экранах доступны возврат назад и отмена, а
раздел «Мои отметки» выводит последние сохранённые записи студента.

VK presentation-адаптер пока не реализован. Его добавление не требует изменения
domain или application handlers.

## 4. Универсальная идентичность

Клиент определяется парой:

```text
provider + external_user_id
```

Поддерживаемые provider:

- `telegram`;
- `vk`;
- `system` — только для системного автора действий, не для регистрации.

Пример Telegram actor:

```python
Actor(
    provider=IdentityProvider.TELEGRAM,
    external_user_id="123456789",
    role=ActorRole.STUDENT,
    student_id=student_id,
)
```

VK-клиент создаёт тот же объект с `IdentityProvider.VK`. Числовые ID платформ
преобразуются в строки на границе presentation-слоя.

## 5. Модель данных

Основные таблицы:

| Таблица | Назначение |
|---|---|
| `students` | Студенты, ФИО, короткое имя, подгруппа, активность |
| `student_roles` | Активные и отозванные роли старосты |
| `external_accounts` | Привязки Telegram/VK к студентам |
| `lessons` | Импортированные и созданные занятия |
| `attendance` | Текущий статус посещаемости |
| `attendance_history` | Неизменяемая история изменения статусов |
| `bonus_requests` | Запросы и решения по использованию `Б` и `У` (историческое имя таблицы) |
| `attendance_settings` | Часовой пояс, лимит `Б`, режим изменения |
| `sheet_mappings` | Координаты студентов и занятий в Sheets |
| `sheet_sync_queue` | Дедуплицированная очередь экспорта |
| `processed_updates` | Идемпотентность событий внешних клиентов |

В `attendance` и `attendance_history` автор хранится как provider и строковый
external ID. Благодаря этому аудит не привязан к Telegram.

## 6. Google Sheets

### 6.1. Поддерживаемая структура

Лист `Журнал`:

| Диапазон | Содержимое |
|---|---|
| `D4:D340` | Предмет |
| `E4:E340` | Подгруппа |
| `F3:AB3` | Короткие ФИО студентов |
| `F4:AB340` | Отметки посещаемости |
| `AC4:AC340` | `Дата_служебная` |

Скрытый лист `Настройки`:

| Диапазон | Содержимое |
|---|---|
| `A2:A` | Полное ФИО |
| `B2:B` | Подгруппа |
| `C2:C` | Короткое ФИО |

Пустая строка предмета означает отсутствие занятия и не импортируется. Цвет
заливки не участвует в бизнес-логике.

В таблице нет номера пары. `sequence_number` вычисляется как технический порядок
непустой строки внутри даты. Его нельзя показывать пользователю как номер пары.

### 6.2. Импорт

Импорт:

- создаёт и обновляет студентов;
- создаёт и обновляет занятия;
- формирует `student_id → sheet_column`;
- формирует `lesson_id → sheet_row`;
- сохраняет fingerprint строки;
- деактивирует исчезнувшие импортированные записи;
- не импортирует статусы из ячеек посещаемости.

Повторный импорт идемпотентен.

### 6.3. Экспорт

Перед записью gateway проверяет:

- короткое ФИО в заголовке столбца;
- дату, предмет, подгруппу и технический порядок строки;
- совпадение вычисленного fingerprint с сохранённым mapping.

После проверки изменяется только одна целевая ячейка. Формулы, стили, отчёты и
остальные ячейки не перезаписываются.

## 7. Очередь синхронизации

На один `attendance_id` существует одна задача с требуемой версией. UPSERT не
позволяет старой версии заменить новую.

Статусы:

- `pending` — ожидает обработки;
- `processing` — захвачена worker;
- `failed` — исчерпаны попытки.

Успешная задача удаляется. Ошибки получают exponential backoff с jitter.
Зависшие `processing`-задачи повторно захватываются после lock timeout.

После обработки исходящей очереди worker периодически читает матрицу
посещаемости. Значения `✓/+`, `Н`, `Б`, `У`, отличающиеся от БД, создают или
изменяют локальную отметку с аудитом от `google_sheets`. Очистка ячейки помечает
существующую отметку удалённой. Ячейки с активной
исходящей задачей пропускаются для защиты от гонки. Пустые ячейки пока не
затрагивают записи, которых ещё нет в БД.

Завершение и ошибка проверяют `processed_version`, поэтому worker не может
удалить более новую задачу.

SQLite рассчитан на один экземпляр worker. Для нескольких параллельных worker
следует использовать PostgreSQL, где применяется `FOR UPDATE SKIP LOCKED`.

## 8. Конфигурация

Настройки читаются из `.env`.

| Переменная | Назначение |
|---|---|
| `BOT_TOKEN` | Токен Telegram-бота |
| `DATABASE_URL` | URL асинхронной БД |
| `GOOGLE_SPREADSHEET_ID` | ID Google-таблицы между `/d/` и `/edit` |
| `GOOGLE_SHEET_NAME` | Имя листа журнала |
| `GOOGLE_SETTINGS_SHEET_NAME` | Имя листа настроек |
| `GOOGLE_CREDENTIALS_FILE` | Путь к JSON service account |
| `DEFAULT_TIMEZONE` | Часовой пояс группы |
| `BONUS_WEEKLY_LIMIT` | Недельный лимит `Б` |
| `ADMIN_TELEGRAM_IDS` | Telegram ID для первичного назначения старосты |
| `SYNC_QUEUE_*` | Batch size, retries, backoff и lock timeout |
| `SHEET_RECONCILIATION_INTERVAL_SECONDS` | Интервал входящей сверки таблицы |
| `LOG_LEVEL` | Уровень JSON-логов (`INFO`, `WARNING`, `DEBUG`) |

JSON service account, `.env` и локальная БД не должны попадать в Git.

### Структурированные логи

`bot`, `worker`, `backup` и ручной импорт используют единый `structlog` JSON-
формат. Логи содержат имя сервиса, UTC timestamp, уровень и тип события. Для
операций добавляются технические идентификаторы `update_id`, `student_id`,
`lesson_id`, `attendance_id`, `bonus_request_id` и версия задачи синхронизации.

ФИО, username, Telegram token, содержимое `.env` и Google credentials не
записываются. Глобальный Telegram error handler сохраняет исключение в журнале,
а пользователю возвращает нейтральное сообщение без внутренних деталей.

Просмотр:

```bash
docker compose logs -f bot worker backup
```

## 9. Локальный запуск

Требования:

- Python 3.12;
- Poetry;
- Google service account с доступом к нужной таблице.

Установка:

```bash
cp .env.example .env
poetry install
poetry run alembic upgrade head
```

Импорт структуры:

```bash
PYTHONPATH=src poetry run python -m import_sheet
```

Одна итерация worker:

```bash
PYTHONPATH=src poetry run python -m sync_worker --once
```

Постоянный worker:

```bash
PYTHONPATH=src poetry run python -m sync_worker
```

Telegram polling:

```bash
PYTHONPATH=src poetry run python -m main
```

### Docker Compose

`compose.yaml` запускает четыре сервиса:

- `migrate` — применяет Alembic-миграции и завершается;
- `bot` — обрабатывает Telegram updates;
- `worker` — постоянно синхронизирует очередь с Google Sheets.
- `backup` — создаёт проверенные консистентные снимки SQLite и выполняет ротацию.

`bot` и `worker` используют одну SQLite-БД `runtime/attendance.db`. SQLite WAL и
`busy_timeout` обеспечивают совместную работу двух процессов. Каталог `secrets`
монтируется read-only и вместе с `.env` не включается в Docker image.

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f bot worker
```

### Резервное копирование и восстановление

`backup` использует SQLite Backup API, поэтому ежедневный снимок остаётся
консистентным при работающих bot и worker, включая режим WAL. Перед сжатием
копия проверяется командой `PRAGMA integrity_check` и атомарно публикуется в
`backups/` как `attendance-YYYYMMDDTHHMMSSZ.sqlite3.gz`.

Настройки:

| Переменная | Назначение |
|---|---|
| `BACKUP_DIR` | Каталог архивов |
| `BACKUP_INTERVAL_SECONDS` | Интервал автоматических снимков |
| `BACKUP_DAILY_RETENTION` | Число последних ежедневных снимков |
| `BACKUP_WEEKLY_RETENTION` | Число сохраняемых недельных снимков |

Ручной снимок:

```bash
docker compose run --rm backup python -m backup
```

Восстановление требует остановки всех процессов, использующих SQLite:

```bash
docker compose stop bot worker backup
docker compose run --rm backup python -m backup \
  --restore /backups/attendance-YYYYMMDDTHHMMSSZ.sqlite3.gz --yes
docker compose up -d bot worker backup
```

Перед восстановлением создаётся аварийный архив `pre-restore-*` текущей БД.

Перед Docker-запуском необходимо остановить локально запущенные `main` и
`sync_worker`: два polling-процесса с одним Telegram-токеном конфликтуют.

## 10. Миграции

Применение:

```bash
poetry run alembic upgrade head
```

Откат последней миграции:

```bash
poetry run alembic downgrade -1
```

Проверка моделей:

```bash
poetry run alembic check
```

Миграция `f4a8d93c2e10` переносит старые Telegram-поля в универсальную модель и
устанавливает `provider=telegram`, сохраняя существующие данные.

## 11. Тестирование и качество

```bash
poetry run pytest -q
poetry run ruff format src tests migrations
poetry run ruff check src tests migrations
```

Покрыты:

- доменные переходы посещаемости и регистрации;
- недельный лимит `Б`;
- отсутствие временного ограничения;
- optimistic locking посещаемости;
- атомарность attendance, history и sync queue;
- дедупликация и retry очереди;
- проверка структуры Sheets перед записью;
- идемпотентный импорт;
- Telegram/VK identity с совпадающими внешними ID.

## 12. Безопасность

- Не коммитить `.env` и каталог `secrets`.
- Не выводить private key и токены в логи.
- Выдавать service account доступ только к нужной таблице.
- Не доверять provider/user ID из callback payload: identity берётся из события
  конкретного presentation-адаптера.
- Проверять роль старосты в application handler, а не только скрывать кнопки.
- Не записывать в Sheets до проверки mapping и fingerprint.

## 13. Текущее состояние

Реализовано:

- модели и миграции БД;
- импорт студентов и занятий;
- универсальная регистрация внешнего аккаунта;
- административная отвязка;
- создание посещаемости и аудит;
- очередь и worker Google Sheets;
- реальная проверка записи одной ячейки в тестовую таблицу.

Ещё предстоит:

- подключить registration commands/queries к aiogram;
- реализовать меню выбора даты, предмета и статуса;
- реализовать административное меню и выдачу роли старосты;
- завершить процесс согласования `Б`;
- реализовать административное исправление отметки;
- добавить обработку конфликтов Sheets;
- настроить Dishka composition root;
- добавить graceful shutdown, healthchecks и структурированные логи;
- реализовать VK presentation-адаптер;
- подготовить Docker/systemd-развёртывание и резервное копирование.
