from dataclasses import dataclass

from domain.common.exceptions import (
    BonusLimitExceededError,
    BonusNotApprovedError,
)


@dataclass(frozen=True, slots=True)
class BonusEligibilityPolicy:
    weekly_limit: int

    def ensure_eligible(self, *, approved: bool, used_count: int) -> None:
        if not approved:
            raise BonusNotApprovedError
        if used_count >= self.weekly_limit:
            raise BonusLimitExceededError
