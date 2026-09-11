"""Final button-routing compatibility layer.

Keeps Telegram menus as inline buttons inside the message while translating
those callbacks into the existing text router without mutating Telegram's
immutable Message objects. Also prevents the admin menu from assuming a
ReplyKeyboardMarkup after the UI layer has converted keyboards to inline.
"""
import copy
import logging
from types import SimpleNamespace

log = logging.getLogger("netyar.button_routing_fix")


class _MessageProxy:
    """Proxy a Telegram Message while exposing a writable text value."""

    def __init__(self, original, text):
        self._original = original
        self.text = text

    def __getattr__(self, name):
        return getattr(self._original, name)



def _fixed_fake_update(update, label):
    q = update.callback_query
    original = q.message
    msg = _MessageProxy(original, label)
    return SimpleNamespace(
        message=msg,
        effective_user=update.effective_user,
        effective_chat=update.effective_chat,
        callback_query=None,
    )


def install():
    import bot as B
    import final_ui_flow_patch as F

    if getattr(B, "_button_routing_fix_installed", False):
        return

    # The previous implementation copied telegram.Message and then assigned
    # .text. python-telegram-bot makes Message fields immutable, so every
    # inline button callback crashed before reaching the real router.
    F._fake_update = _fixed_fake_update

    # business_flow_patch expects ReplyKeyboardMarkup.keyboard. After the
    # inline UI conversion the object is InlineKeyboardMarkup instead. Replace
    # only the public admin-menu builder with a stable source-of-truth layout.
    def safe_amenu():
        return B.kb([
            ["👤 پنل کاربران", "👥 همکاران"],
            ["💰 شارژها", "💳 پرداخت‌های مشتری"],
            ["📋 درخواست‌ها", "⚙️ قیمت‌ها"],
            ["➕ افزایش اعتبار", "➖ کاهش اعتبار"],
            ["📊 گزارش"],
            ["🤖 افزودن بات", "🤖 بات‌های متصل"],
            ["⬅️ منوی اصلی"],
        ])

    B.amenu = safe_amenu
    B._button_routing_fix_installed = True
    log.info("final Telegram button routing compatibility installed")
