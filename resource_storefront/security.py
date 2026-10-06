import hashlib
import os
import secrets

from django.db import transaction
from django.utils import timezone
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .models import WholesaleAccessLink


def _cipher():
    key = getattr(settings, "RESOURCE_TOKEN_ENCRYPTION_KEY", "")
    if not key:
        raise ImproperlyConfigured("RESOURCE_TOKEN_ENCRYPTION_KEY must be configured to issue or recover buyer links")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        raise ImproperlyConfigured("RESOURCE_TOKEN_ENCRYPTION_KEY must be a Fernet URL-safe base64 key") from None


def issue_link(contact, actor):
    token = secrets.token_urlsafe(48)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    cipher = _cipher()
    with transaction.atomic():
        WholesaleAccessLink.objects.filter(contact=contact, is_active=True).update(is_active=False, revoked_at=timezone.now())
        link = WholesaleAccessLink.objects.create(
            contact=contact, token_digest=digest,
            encrypted_token=cipher.encrypt(token.encode()).decode("ascii"), created_by=actor,
        )
    return link, token


def recover_token(link):
    try:
        return _cipher().decrypt(link.encrypted_token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ImproperlyConfigured):
        return None


def contact_for_request(request):
    contact_id = request.session.get("resource_contact_id")
    if not contact_id:
        return None
    if request.user.is_authenticated:
        contact = __import__("resource_storefront.models", fromlist=["WholesaleContact"]).WholesaleContact.objects.filter(pk=contact_id, is_archived=False).first()
        return contact
    link_id = request.session.get("resource_link_id")
    return WholesaleAccessLink.objects.filter(
        pk=link_id, contact_id=contact_id, is_active=True, contact__is_archived=False,
    ).select_related("contact").values_list("contact", flat=True).first() and WholesaleAccessLink.objects.get(pk=link_id).contact


def enter_buyer_session(request, link):
    previous_contact = request.session.get("resource_contact_id")
    request.session.cycle_key()
    if previous_contact != link.contact_id:
        for key in ("resource_cart", "resource_cart_seen", "resource_checkout_key", "resource_checkout_draft", "resource_cart_operations"):
            request.session.pop(key, None)
        request.session.pop("resource_staff_preview", None)
    request.session["resource_contact_id"] = link.contact_id
    request.session["resource_link_id"] = link.pk
    request.session.set_expiry(60 * 60 * 24 * 30)


def validate_buyer(request):
    link_id = request.session.get("resource_link_id")
    contact_id = request.session.get("resource_contact_id")
    if not link_id or not contact_id:
        return None
    link = WholesaleAccessLink.objects.select_related("contact").filter(
        pk=link_id, contact_id=contact_id, is_active=True, contact__is_archived=False,
    ).first()
    if not link:
        request.session.pop("resource_contact_id", None)
        request.session.pop("resource_link_id", None)
        request.session.pop("resource_cart", None)
        request.session.pop("resource_cart_seen", None)
        request.session.pop("resource_checkout_key", None)
        return None
    request.wholesale_access_link_id = link.pk
    return link.contact
