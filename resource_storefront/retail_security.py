import hashlib
import logging
import secrets
import uuid

from django.db import transaction
from django.views.decorators.debug import sensitive_variables
from .models import RetailSettings
from .security import _cipher

logger = logging.getLogger("gamebat.business")


@sensitive_variables("token")
@transaction.atomic
def retail_link(*, actor=None, regenerate=False):
    config, _ = RetailSettings.objects.get_or_create(pk=1)
    config = RetailSettings.objects.select_for_update().get(pk=1)
    if regenerate or not config.token_digest:
        token = secrets.token_urlsafe(48)
        config.token_digest = hashlib.sha256(token.encode()).hexdigest()
        config.encrypted_token = _cipher().encrypt(token.encode()).decode("ascii")
        config.generation = uuid.uuid4()
        config.save(update_fields=("token_digest", "encrypted_token", "generation", "updated_at"))
        logger.info("Розничная ссылка выпущена: user_id=%s", getattr(actor, "pk", None))
    return config


def validate_retail(request):
    generation = request.session.get("retailer_generation")
    if not generation:
        return False
    valid = RetailSettings.objects.filter(pk=1, generation=generation).exclude(token_digest="").exists()
    if not valid:
        request.session.pop("retailer_generation", None)
    return valid


def enter_retail(request, config):
    request.session.cycle_key()
    request.session["retailer_generation"] = str(config.generation)
    if not request.session.get("retailer_visitor"):
        request.session["retailer_visitor"] = str(uuid.uuid4())
    request.session.set_expiry(60 * 60 * 24 * 30)
