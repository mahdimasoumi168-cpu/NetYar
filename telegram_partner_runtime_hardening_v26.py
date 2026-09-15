"""Final partner runtime hardening.

Management chat is a real waiting mode: the button only changes state; the
first actual partner message/media is consumed here before legacy handlers can
turn it into a generic ui2 execution error. Night-shift authenticated partners
also keep their session while entering service data; the closed-hours gate must
not reject a valid partner merely because the current service changed mode.

This layer also hardens legacy Telegram handlers: synchronous callbacks are
adapted to async callbacks (preventing ``NoneType can't be used in await``),
and the legacy management dispatcher is patched so its ApplicationHandlerStop
cannot be converted into the user's generic execution-error message.
"""
import inspect
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.partner_runtime_hardening_v26")
MANAGEMENT = "💬 ارتباط با مدیریت"
CANCEL = "❌ انصراف"


def _admin_ids(B):
    out = []
    for src in (getattr(B, "ADM", ()), getattr(B, "ADMINS", ())):
        for value in src or ():
            try:
                n = int(value)
                if n not in out:
                    out.append(n)
            except Exception:
                pass
    return out


def _partner_kb(B, uid):
    try:
        return B.partner_kb_for(uid, "fa")
    except Exception:
        try:
            import telegram_ui_policy_v2 as UI
            return UI.inline([
                ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
                ["📱 حل مشکل سیم کارت ایرانسل", "🪪 فیدای غیر حضوری"],
                ["📱 خدمات سیم کارت", "🔎 پیگیری کد"],
                ["📋 سوابق", "💰 موجودی"],
                ["🎫 تیکت به مدیریت", MANAGEMENT],
                ["🚪 خروج از پنل"],
                [CANCEL],
            ], B, uid)
        except Exception:
            return None


def _chat_kb(B, uid):
    return InlineKeyboardMarkup([[InlineKeyboardButton(CANCEL, callback_data="partner_chat_cancel")]])


def _resolve_admin(B, uid):
    st = B.S.setdefault(uid, {})
    for value in (st.get("final_chat_admin"), st.get("management_chat_id"), *_admin_ids(B)):
        try:
            n = int(value)
            st["final_chat_admin"] = n
            st["management_chat_id"] = n
            return n
        except Exception:
            pass
    return None


def _active_partner(B, uid):
    st = B.S.setdefault(uid, {})
    if st.get("partner_logged_out") or not st.get("partner_active") or not st.get("partner_id"):
        return False
    try:
        row = B.db.conn.execute(
            "SELECT id FROM partners WHERE id=? AND active=1 LIMIT 1", (int(st["partner_id"]),)
        ).fetchone()
        return bool(row)
    except Exception:
        return False


async def _safe_management_dispatch(update, context, B, original):
    """Run the legacy management dispatch without leaking ApplicationHandlerStop.

    The old ui2 callback catches ApplicationHandlerStop as a normal Exception and
    turns it into the exact generic error the partner was seeing.  We perform the
    same state transition here but deliberately return normally.
    """
    q = getattr(update, "callback_query", None)
    if not q:
        return await original(update, context, B, MANAGEMENT)
    uid = q.from_user.id
    st = B.S.setdefault(uid, {})
    pid = st.get("partner_id")
    active = bool(pid and st.get("partner_active", False) and not st.get("partner_logged_out", False))
    if not active:
        await q.message.reply_text("⛔ ابتدا وارد پنل همکاران شوید.", reply_markup=_partner_kb(B, uid))
        return None
    try:
        row = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)).fetchone()
    except Exception:
        row = None
    if not row:
        st.pop("partner_id", None)
        st["partner_active"] = False
        st["mode"] = None
        await q.message.reply_text("⛔ حساب همکار فعال نیست. لطفاً دوباره وارد شوید.", reply_markup=B.main(uid))
        return None
    admin_id = None
    for value in (st.get("final_chat_admin"), st.get("management_chat_id"), *_admin_ids(B)):
        try:
            admin_id = int(value)
            break
        except Exception:
            pass
    if not admin_id:
        await q.message.reply_text(
            "⚠️ ارتباط با مدیریت در حال حاضر مقصد مشخصی ندارد.\n"
            "پنل شما باز است و می‌توانید بعداً دوباره تلاش کنید.",
            reply_markup=_partner_kb(B, uid),
        )
        return None
    st.update(
        mode="final_partner_chat",
        final_chat_admin=admin_id,
        final_chat_partner_id=int(pid),
        management_chat_id=admin_id,
        chat_reply_pending=False,
    )
    try:
        B.db.set_setting(f"partner_chat_{int(pid)}", str(uid))
        if row["phone"]:
            B.db.set_setting(f"partner_chat_{row['phone']}", str(uid))
        B.db.set_setting(f"final_chat_admin_{int(pid)}", str(admin_id))
    except Exception:
        log.exception("safe management mapping save failed")
    await q.message.reply_text(
        "💬 ارتباط با مدیریت فعال شد.\n\n"
        "حالا پیام خود را ارسال کنید.\n"
        "متن، عکس، فایل، ویس یا ویدیو قابل ارسال است.\n\n"
        "⏳ تا وقتی چیزی ارسال نکنید، هیچ پیامی برای مدیریت فرستاده نمی‌شود.\n"
        "برای پایان ارتباط، «❌ انصراف» را بزنید.",
        reply_markup=B.cancel_kb(st.get("lang", "fa")),
    )
    return None


def _patch_legacy_dispatch(B):
    """Patch telegram_ui_policy_v2._dispatch at the global lookup point.

    Existing wrapper layers call the module global, so this fixes the actual
    callback chain even when an older handler reaches the canonical ui2 owner.
    """
    try:
        import telegram_ui_policy_v2 as UI
        if getattr(UI, "_netyar_management_dispatch_v26", False):
            return
        old = UI._dispatch

        async def dispatch(update, context, Bot, label):
            if str(label).strip() in {MANAGEMENT, "💬 Contact management", "💬 التواصل مع الإدارة"}:
                return await _safe_management_dispatch(update, context, Bot, old)
            return await old(update, context, Bot, label)

        UI._dispatch = dispatch
        UI._netyar_management_dispatch_v26 = True
        log.info("Legacy ui2 management dispatch patched")
    except Exception:
        log.exception("Failed to patch legacy ui2 management dispatch")


def _adapt_sync_handlers(app):
    """Prevent PTB from awaiting a synchronous legacy callback returning None."""
    try:
        for group, handlers in list(getattr(app, "handlers", {}).items()):
            for handler in list(handlers or []):
                cb = getattr(handler, "callback", None)
                if not callable(cb) or getattr(cb, "_netyar_async_adapter_v26", False):
                    continue
                if inspect.iscoroutinefunction(cb):
                    continue

                async def adapted(update, context, _cb=cb):
                    result = _cb(update, context)
                    if inspect.isawaitable(result):
                        return await result
                    return result

                adapted._netyar_async_adapter_v26 = True
                handler.callback = adapted
        log.info("Legacy synchronous Telegram callbacks adapted")
    except Exception:
        log.exception("Legacy callback adaptation failed")


def install(app, B):
    if getattr(B, "_partner_runtime_hardening_v26", False):
        return

    _patch_legacy_dispatch(B)
    _adapt_sync_handlers(app)

    async def cancel_callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q or str(q.data or "") != "partner_chat_cancel":
            return
        uid = q.from_user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != "final_partner_chat":
            return
        await q.answer()
        st["mode"] = "partner"
        st["chat_reply_pending"] = False
        await q.message.reply_text("↩️ ارتباط با مدیریت پایان یافت.", reply_markup=_partner_kb(B, uid))
        raise ApplicationHandlerStop

    async def content(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user:
            return
        uid = user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != "final_partner_chat":
            return
        if not _active_partner(B, uid):
            st["mode"] = None
            await msg.reply_text("⛔ نشست همکار معتبر نیست. لطفاً دوباره وارد پنل همکاران شوید.", reply_markup=B.main(uid))
            raise ApplicationHandlerStop

        if getattr(msg, "text", None) and msg.text.strip() == CANCEL:
            st["mode"] = "partner"
            st["chat_reply_pending"] = False
            await msg.reply_text("↩️ ارتباط با مدیریت پایان یافت.", reply_markup=_partner_kb(B, uid))
            raise ApplicationHandlerStop

        admin = _resolve_admin(B, uid)
        if not admin:
            await msg.reply_text("⚠️ مقصد مدیریت تنظیم نشده است. پنل همکاران شما باز ماند؛ بعداً دوباره تلاش کنید.", reply_markup=_chat_kb(B, uid))
            raise ApplicationHandlerStop

        try:
            if getattr(msg, "photo", None):
                await context.bot.send_photo(chat_id=admin, photo=msg.photo[-1].file_id, caption="👥 پیام تصویری از همکار")
            elif getattr(msg, "document", None):
                await context.bot.send_document(chat_id=admin, document=msg.document.file_id, caption="👥 فایل از همکار")
            elif getattr(msg, "voice", None):
                await context.bot.send_voice(chat_id=admin, voice=msg.voice.file_id, caption="👥 ویس از همکار")
            elif getattr(msg, "video", None):
                await context.bot.send_video(chat_id=admin, video=msg.video.file_id, caption="👥 ویدیو از همکار")
            elif getattr(msg, "audio", None):
                await context.bot.send_audio(chat_id=admin, audio=msg.audio.file_id, caption="👥 صوت از همکار")
            elif getattr(msg, "text", None):
                await context.bot.send_message(chat_id=admin, text=f"👥 پیام همکار\n\n{msg.text.strip()}")
            else:
                await msg.reply_text("⚠️ این نوع پیام قابل ارسال نیست. متن، عکس، فایل، ویس یا ویدیو بفرستید.", reply_markup=_chat_kb(B, uid))
                raise ApplicationHandlerStop
            await msg.reply_text("✅ پیام شما برای مدیریت ارسال شد.", reply_markup=_chat_kb(B, uid))
        except Exception:
            log.exception("management content relay failed")
            await msg.reply_text("❌ ارسال به مدیریت انجام نشد؛ پنل شما باز است. دوباره تلاش کنید.", reply_markup=_chat_kb(B, uid))
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(cancel_callback, pattern=r"^partner_chat_cancel$"), group=-100000)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, content), group=-99999)
    B._partner_runtime_hardening_v26 = True
    log.info("Partner runtime hardening v26 installed")
