from uuid import uuid4

from presentation.telegram.callbacks import ConfirmUnlinkAccountCallback


def test_confirm_unlink_account_callback_fits_telegram_limit() -> None:
    packed = ConfirmUnlinkAccountCallback(registration_id=str(uuid4())).pack()

    assert len(packed.encode()) <= 64
