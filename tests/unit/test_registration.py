from datetime import UTC, datetime
from uuid import uuid4

import pytest

from domain.registration import Registration, RegistrationStatus
from domain.vo.actor import IdentityProvider


def test_registration_is_active_immediately_and_can_be_unlinked() -> None:
    now = datetime(2026, 9, 16, 12, tzinfo=UTC)
    registration = Registration.register(
        registration_id=uuid4(),
        student_id=uuid4(),
        provider=IdentityProvider.TELEGRAM,
        external_user_id="42",
        username="student",
        now=now,
    )

    assert registration.status is RegistrationStatus.APPROVED
    registration.unlink(now=now)
    assert registration.status is RegistrationStatus.UNLINKED
    assert registration.unlinked_at == now


def test_only_approved_registration_can_be_unlinked() -> None:
    now = datetime(2026, 9, 16, 12, tzinfo=UTC)
    registration = Registration.register(
        registration_id=uuid4(),
        student_id=uuid4(),
        provider=IdentityProvider.VK,
        external_user_id="42",
        username=None,
        now=now,
    )

    registration.unlink(now=now)
    with pytest.raises(ValueError, match="only an approved"):
        registration.unlink(now=now)
