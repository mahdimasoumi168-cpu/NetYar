"""Final button-routing compatibility layer.

Keeps Telegram menus as inline buttons while translating callbacks into the
existing text router without copying or mutating Telegram Message objects.
"""
import logging
from types import SimpleNamespace

log = logging.getLogger("netyar.button_routing_fix")


class _MessageProxy:
    """Small, copy-safe proxy exposing a writable text value."""

    __slots__ = ("_original", "text")

    def __init__(self, original, text):
        # Never wrap our own proxy. Nested proxies were the source of the
        # RecursionError seen when copy.copy() inspected __getattr__.
        while isinstance(original, _MessageProxy):
            original = object.__getattribute__(original, "_original")
        object.__setattr__(self, "_original", original)
        object.__setattr__(self, "text", text)

    def __getattribute__(self, name):
        if name in {"_original", "text", "__class__", "__slots__", "__dict__"}:
            return object.__getattribute__(self, name)
        original = object.__getattribute__(self, "_original")
        return getattr(original, name)

    def __setattr__(self, name, value):
        if name == "text":
            object.__setattr__(self, name, value)
            return
        setattr(object.__getattribute__(self, "_original"), name, value)

    def __copy__(self):
        return _MessageProxy(
            object.__getattribute__(self, "_original"),
            object.__getattribute__(self, "text"),
        )

    def __deepcopy__(self, memo):
        return self.__copy__()


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

    # Replace the old implementation that used copy.copy(Message) followed by
    # assignment to .text. PTB Message objects are immutable and that approach
    # can recursively invoke __getattr__ when multiple patches are installed.
    F._fake_update = _fixed_fake_update

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
