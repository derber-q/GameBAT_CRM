"""Одноразовая привязка числового Telegram ID; контакты User.telegram не используются."""
from datetime import timedelta
import hashlib
import secrets
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from core.db_retry import retry_database_lock
from .models import StaffBot, StaffBotAccess, StaffBotLink


class BotDenied(ValidationError):
    def __init__(self, category='denied', message='Доступ закрыт. Проверьте привязку и разрешения в CRM.'):
        self.category = category
        super().__init__(message)


def check_access(access, *, require_link=True):
    """Новый User на каждой проверке исключает устаревший кэш Django permissions."""
    try:
        access.refresh_from_db()
    except StaffBotAccess.DoesNotExist:
        raise BotDenied() from None
    user = get_user_model().objects.filter(pk=access.user_id, is_active=True).first()
    bot = StaffBot.objects.get(pk=access.bot_id)
    if (bot.code != 'staff' or not bot.enabled or not access.allowed or access.revoked_at
            or (require_link and not access.telegram_user_id) or not user
            or not user.has_perm('telegram_bots.use_staff_bot')):
        raise BotDenied()
    return user


def check_function_access(access, function, *, require_link=True):
    from .menu import FUNCTIONS, SUPPLIER_TEMPLATES
    user = check_access(access, require_link=require_link)
    item = FUNCTIONS.get(function)
    if item is None or not item.allowed(user):
        message = ('У вас нет разрешения на скачивание шаблонов поставщиков.'
            if function == SUPPLIER_TEMPLATES.code else 'У вас нет разрешения на формирование оптового прайса.')
        raise BotDenied('function_denied', message)
    return user


def authorize(bot, telegram_id):
    access = StaffBotAccess.objects.filter(bot=bot, telegram_user_id=telegram_id).first()
    if not access:
        raise BotDenied()
    return access, check_access(access)


@retry_database_lock
@transaction.atomic
def issue_link(user, bot):
    bot = StaffBot.objects.select_for_update().get(pk=bot.pk)
    access = StaffBotAccess.objects.filter(bot=bot, user=user).first()
    if not access:
        raise BotDenied()
    check_access(access, require_link=False)
    if access.telegram_user_id:
        raise BotDenied('already_linked', 'Telegram уже привязан. Для замены сначала отключите привязку.')
    now = timezone.now()
    for old in access.staffbotlink_set.filter(used_at__isnull=True):
        old.used_at = now
        old.save(update_fields=['used_at'])
    token = secrets.token_urlsafe(32)
    StaffBotLink.objects.create(access=access, token_hash=hashlib.sha256(token.encode()).hexdigest(),
                               expires_at=now + timedelta(minutes=10))
    return f'https://t.me/{bot.username}?start={token}'


def consume_link(bot, token, telegram_id, username=''):
    """Вызывается внутри атомарного приёма update с блокировкой конкретного бота."""
    if not isinstance(token, str) or not 20 <= len(token) <= 64:
        raise BotDenied('invalid_link', 'Ссылка подключения недействительна или уже использована.')
    link = StaffBotLink.objects.select_related('access').filter(access__bot=bot,
        token_hash=hashlib.sha256(token.encode()).hexdigest(), used_at__isnull=True,
        expires_at__gt=timezone.now()).first()
    if not link:
        raise BotDenied('invalid_link', 'Ссылка подключения недействительна или уже использована.')
    access = link.access
    check_access(access, require_link=False)
    if access.telegram_user_id or StaffBotAccess.objects.filter(bot=bot, telegram_user_id=telegram_id).exists():
        raise BotDenied('identity_in_use', 'Telegram уже привязан. Обратитесь к администратору CRM.')
    access.telegram_user_id, access.username = telegram_id, str(username)[:64]
    access.linked_at, access.revoked_at = timezone.now(), None
    access.save(update_fields=['telegram_user_id', 'username', 'linked_at', 'revoked_at'])
    link.used_at = timezone.now()
    link.save(update_fields=['used_at'])
    return access


@retry_database_lock
@transaction.atomic
def set_employee_access(actor, bot, user, allowed):
    if not actor.is_active or not actor.is_superuser:
        raise PermissionDenied
    StaffBot.objects.select_for_update().get(pk=bot.pk)
    access, _ = StaffBotAccess.objects.get_or_create(bot=bot, user=user)
    access.allowed = allowed
    if allowed:
        from django.contrib.auth.models import Permission
        user.user_permissions.add(Permission.objects.get(content_type__app_label='telegram_bots', codename='use_staff_bot'))
        access.revoked_at = None
    else:
        access.revoked_at = timezone.now()
        access.telegram_user_id, access.username = None, ''
        for link in access.staffbotlink_set.filter(used_at__isnull=True):
            link.used_at = timezone.now()
            link.save(update_fields=['used_at'])
    access.save()
    return access
