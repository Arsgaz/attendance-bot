from adapter.database.models import ExternalAccountModel
from domain.registration import Registration, RegistrationStatus
from domain.vo.actor import IdentityProvider


def registration_to_domain(model: ExternalAccountModel) -> Registration:
    return Registration(
        id=model.id,
        student_id=model.student_id,
        provider=IdentityProvider(model.provider),
        external_user_id=model.external_user_id,
        username=model.username,
        status=RegistrationStatus(model.status),
        unlinked_at=model.unlinked_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
