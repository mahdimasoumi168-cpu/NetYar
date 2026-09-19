"""Final Telegram UI guard.
Keeps a persistent Start-again button below the chat and makes the Iranian
Contact-us option reachable through the canonical router.
"""
import logging
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, CallbackQueryHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.final_ui_guard")
RESTART = "🔄 شروع مجدد"
CONTACT = "📞 تماس با ما"


def _restart_kb():
    # is_persistent keeps this keyboard available while the user moves through
    # inline/reply menus and multi-step forms.
    return ReplyKeyboardMarkup([[RESTART]], resize_keyboard=True, is_persistent=True)


def _install_persistent_restart(B):
    # Canonical UI policy already converts menu buttons to InlineKeyboardMarkup
    # so every menu stays attached to its message. Do NOT wrap B.kb back into
    # ReplyKeyboardMarkup here; that would put menu buttons under the chat.
    # The only persistent ReplyKeyboard is the dedicated «🔄 شروع مجدد» key.
    if getattr(B, "_inline_ui_v2", False):
        B._persistent_restart_kb_wrapped = True
        return
    if callable(getattr(B, "kb", None)) and not getattr(B, "_persistent_restart_kb_wrapped", False):
        original_kb = B.kb
        def kb(rows):
            result = original_kb(rows)
            # Preserve an already-inline canonical menu.
            if isinstance(result, InlineKeyboardMarkup):
                return result
            normalized = [list(r) for r in (rows or [])]
            if not any(RESTART in row for row in normalized):
                normalized.append([RESTART])
            return ReplyKeyboardMarkup(normalized, resize_keyboard=True, is_persistent=True)
        B.kb = kb
        B._persistent_restart_kb_wrapped = True


async def _restart_text(update, context, B):
    message = getattr(update, "message", None)
    uid = getattr(getattr(update, "effective_user", None), "id", None)
    if message is None or uid is None:
        return
    try:
        from telegram_runtime_clean import _restart
        await _restart(update, context)
    except ApplicationHandlerStop:
        raise
    except Exception:
        log.exception("persistent restart failed")
        try:
            await message.reply_text(
                "🔄 منو دوباره آماده شد.",
                reply_markup=_restart_kb(),
            )
        except Exception:
            pass
    raise ApplicationHandlerStop


async def _restart_callback(update, context, B):
    q = getattr(update, "callback_query", None)
    if q is None:
        return
    try:
        await q.answer()
    except Exception:
        pass
    try:
        from telegram_runtime_clean import _restart
        await _restart(update, context)
    except ApplicationHandlerStop:
        raise
    except Exception:
        log.exception("inline restart failed")
        await q.message.reply_text("🔄 منو دوباره آماده شد.", reply_markup=_restart_kb())
    raise ApplicationHandlerStop


async def _iranian_contact(update, context, B):
    q = getattr(update, "callback_query", None)
    message = getattr(update, "message", None) or getattr(q, "message", None)
    uid = getattr(getattr(update, "effective_user", None), "id", None)
    if message is None or uid is None:
        return
    st = B.S.setdefault(uid, {})
    if st.get("status") != "iranian":
        return
    url_user = str(__import__("os").getenv("CONTACT_USERNAME", "Good_ok_2000")).strip().lstrip("@")
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📞 ارتباط با پشتیبانی", url=f"https://t.me/{url_user}")]
    ])
    await message.reply_text(
        "📞 تماس با ما\n\nبرای ارتباط با پشتیبانی روی دکمه زیر بزنید:",
        reply_markup=markup,
    )
    await message.reply_text("🔄 دکمه شروع مجدد همیشه فعال است.", reply_markup=_restart_kb())
    raise ApplicationHandlerStop


def install(app, B):
    if getattr(B, "_final_ui_guard_v1", False):
        return
    _install_persistent_restart(B)

    # Highest-priority text route: it wins over legacy router layers.
    app.add_handler(
        MessageHandler(filters.Regex(r"^🔄 شروع مجدد$"), lambda u, c: _restart_text(u, c, B)),
        group=-20000000,
    )
    app.add_handler(
        CallbackQueryHandler(lambda u, c: _restart_callback(u, c, B), pattern=r"^start:restart$"),
        group=-20000000,
    )
    app.add_handler(
        MessageHandler(filters.Regex(r"^📞 تماس با ما$"), lambda u, c: _iranian_contact(u, c, B)),
        group=-19999999,
    )
    B._persistent_restart_markup = _restart_kb
    B._final_ui_guard_v1 = True
    log.info("FINAL UI GUARD: persistent restart + Iranian contact installed")
