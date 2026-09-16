import pytest

from domain.attendance.policies import BonusEligibilityPolicy
from domain.common.exceptions import (
    BonusLimitExceededError,
    BonusNotApprovedError,
)


def test_bonus_requires_approval_and_free_limit() -> None:
    policy = BonusEligibilityPolicy(weekly_limit=3)
    with pytest.raises(BonusNotApprovedError):
        policy.ensure_eligible(approved=False, used_count=0)
    with pytest.raises(BonusLimitExceededError):
        policy.ensure_eligible(approved=True, used_count=3)
    policy.ensure_eligible(approved=True, used_count=2)
