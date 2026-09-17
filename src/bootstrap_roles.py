import asyncio
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select

from adapter.clock.system import SystemClock
from adapter.database.engine import create_engine, create_session_factory
from adapter.database.models import ExternalAccountModel, StudentRoleModel
from config.settings import Settings
from domain.vo.actor import IdentityProvider
from observability import configure_logging, get_logger

logger = get_logger(__name__)


async def run() -> None:
    settings = Settings()  # type: ignore[call-arg]
    configure_logging(
        service="bootstrap-roles",
        level=settings.log_level,
        pseudonym_key=settings.observability_hash_key.get_secret_value(),
    )
    configured = {
        IdentityProvider.TELEGRAM: {
            str(value) for value in settings.bootstrap_owner_telegram_ids
        },
        IdentityProvider.VK: {str(value) for value in settings.bootstrap_owner_vk_ids},
    }
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    clock = SystemClock(ZoneInfo(settings.default_timezone))
    created = 0
    missing = 0
    try:
        async with session_factory() as session:
            student_ids = set()
            for provider, external_ids in configured.items():
                for external_id in external_ids:
                    student_id = await session.scalar(select(ExternalAccountModel.student_id).where(
                        ExternalAccountModel.provider == provider.value,
                        ExternalAccountModel.external_user_id == external_id,
                        ExternalAccountModel.status == "approved",
                    ))
                    if student_id is None:
                        missing += 1
                        logger.warning(
                            "bootstrap_owner_account_not_found",
                            provider=provider.value,
                            external_user_id=external_id,
                        )
                    else:
                        student_ids.add(student_id)
            for student_id in student_ids:
                existing = await session.scalar(select(StudentRoleModel.id).where(
                    StudentRoleModel.student_id == student_id,
                    StudentRoleModel.role == "owner",
                    StudentRoleModel.revoked_at.is_(None),
                ))
                if existing is not None:
                    continue
                session.add(StudentRoleModel(
                    id=uuid4(),
                    student_id=student_id,
                    role="owner",
                    assigned_at=clock.now(),
                    assigned_by_student_id=student_id,
                    revoked_at=None,
                    revoked_by_student_id=None,
                ))
                created += 1
            await session.commit()
    finally:
        await engine.dispose()
    logger.info("bootstrap_owner_roles_completed", created=created, missing=missing)


if __name__ == "__main__":
    asyncio.run(run())
