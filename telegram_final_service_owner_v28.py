"""Final Telegram service/menu owner.

Loaded after all legacy overlays. Owns the partner keyboard and the two
problematic partner actions so older callback wrappers cannot hide the
Irancell service or leak a generic ui2 error.
"""
import inspect
import logging
from telegram import InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.final_service_owner_v28")
MANAGEMENT = "💬 ارتباط با مدیریت"
IRANCELL = "📱 حل مشکل سیم کارت ایرانسل"
SIM_SERVICE = "📱 خدمات سیم کارت"
CANCEL = "❌ انصراف"
PRICE = 980_000
PHONE_MODE = "irancell_partner_phone"


def _partner_markup(B, uid):
    import telegram_ui_policy_v2 as UI
    return UI.inline([
        ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
        [IRANCELL, "🪪 فیدای غیر حضوری"],
        [SIM_SERVICE, "🔎 پیگیری کد"],
        ["📋 سوابق", "💰 موجودی"],
        ["🎫 تیکت به مدیریت", MANAGEMENT],
        ["🚪 خروج از پنل"],
        [CANCEL],
    ], B, uid)


def _admin(B):
    for name in ("ADM", "ADMINS"):
        for value in getattr(B, name, ()) or ():
            try:
                return int(value)
            except Exception:
                pass
    return None


async def _management(update, context, B, q, st):
    uid = q.from_user.id
    pid = st.get("partner_id")
    if not pid or not st.get("partner_active", False) or st.get("partner_logged_out"):
        await q.message.reply_text("⛔ ابتدا وارد پنل همکاران شوید.", reply_markup=_partner_markup(B, uid))
        raise ApplicationHandlerStop
    row = B.db.conn.execute("SELECT id,name,phone FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)).fetchone()
    if not row:
        st.update(partner_active=False, mode=None)
        st.pop("partner_id", None)
        await q.message.reply_text("⛔ حساب همکار فعال نیست. لطفاً دوباره وارد شوید.", reply_markup=B.main(uid))
        raise ApplicationHandlerStop
    admin_id = _admin(B)
    if not admin_id:
        await q.message.reply_text("❌ مدیر برای ارتباط با مدیریت تنظیم نشده است.", reply_markup=_partner_markup(B, uid))
        raise ApplicationHandlerStop
    try:
        B.db.set_setting(f"partner_chat_{int(pid)}", str(uid))
        if row["phone"]:
            B.db.set_setting(f"partner_chat_{row['phone']}", str(uid))
        B.db.set_setting(f"final_chat_admin_{int(pid)}", str(admin_id))
    except Exception:
        log.exception("management mapping save failed")
    st.update(mode="final_partner_chat", final_chat_admin=int(admin_id), final_chat_partner_id=int(pid), chat_reply_pending=False)
    try:
        await context.bot.send_message(
            chat_id=int(admin_id),
            text=(f"💬 ارتباط با مدیریت از طرف همکار فعال شد.\n\n👤 همکار: {row['name'] or '-'}\n"
                  f"📱 شماره همکار: {row['phone'] or '-'}\n🆔 شناسه همکار: {int(pid)}\n\n"
                  "پیام، عکس، فایل، ویس یا ویدیو همکار برای شما ارسال می‌شود."),
        )
    except Exception:
        log.exception("management notification failed")
    await q.message.reply_text(
        "💬 ارتباط با مدیریت فعال شد.\n\nحالا پیام، عکس، فایل، ویس یا ویدیو را ارسال کنید.\n"
        "پیام‌ها مستقیماً برای مدیریت ارسال می‌شوند.\n\nبرای پایان ارتباط، «❌ انصراف» را بزنید.",
        reply_markup=B.cancel_kb(st.get("lang", "fa")),
    )
    raise ApplicationHandlerStop


async def _irancell(update, context, B, q, st):
    uid = q.from_user.id
    pid = st.get("partner_id")
    if not pid or not st.get("partner_active", False) or st.get("partner_logged_out"):
        await q.message.reply_text("⛔ ابتدا وارد پنل همکاران شوید.", reply_markup=_partner_markup(B, uid))
        raise ApplicationHandlerStop
    try:
        import telegram_irancell_partner_service as IRSIM
        IRSIM.PRICE = PRICE
        IRSIM._ensure_service(B)
        try:
            B.db.conn.execute("UPDATE services SET price=?, active=1 WHERE key=?", (PRICE, "irancell_sim_issue"))
            B.db.conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", ("price_irancell_sim", str(PRICE)))
            B.db.conn.commit()
        except Exception:
            try: B.db.conn.rollback()
            except Exception: pass
    except Exception:
        log.exception("Irancell service registration failed")
    st["mode"] = PHONE_MODE
    st.pop("irancell", None)
    await q.message.reply_text(
        "📱 حل مشکل سیم کارت ایرانسل\n\n"
        "📱 شماره موبایل ایرانسل که به نام مشترک ثبت شده است را وارد کنید:\n\n"
        "💰 هزینه خدمت: ۹۸۰٬۰۰۰ تومان\n"
        "💳 مبلغ فقط از شارژ پنل همکار کسر می‌شود.\n\n"
        "بعد از ثبت، درخواست همراه با مدرک و جزئیات برای مدیریت ارسال می‌شود.",
        reply_markup=B.cancel_kb(st.get("lang", "fa")),
    )
    raise ApplicationHandlerStop


def install(app, B):
    if getattr(B, "_final_service_owner_v28", False):
        return
    import telegram_ui_policy_v2 as UI
    UI.MANAGEMENT = MANAGEMENT
    UI.IRANCELL = IRANCELL
    old_dispatch = UI._dispatch

    async def dispatch(update, context, BB, label):
        label = str(label or "").strip()
        q = getattr(update, "callback_query", None)
        if q and label == MANAGEMENT:
            return await _management(update, context, BB, q, BB.S.setdefault(q.from_user.id, {}))
        if q and label == IRANCELL:
            return await _irancell(update, context, BB, q, BB.S.setdefault(q.from_user.id, {}))
        result = old_dispatch(update, context, BB, label)
        if inspect.isawaitable(result):
            return await result
        return result

    UI._dispatch = dispatch
    UI._final_service_owner_v28_dispatch = True
    B.partner_kb = lambda lang="fa": _partner_markup(B, int(UI._uid() or 0))

    async def callback(update, context):
        q = getattr(update, "callback_query", None)
        if not q or not str(q.data or "").startswith("ui2:"):
            return
        token = str(q.data)[4:]
        row = B.db.conn.execute("SELECT user_id,label,lang,status FROM ui2_callbacks WHERE token=? LIMIT 1", (token,)).fetchone()
        label = str(row["label"] or "").strip() if row else ""
        if not label:
            try:
                for rr in getattr(q.message.reply_markup, "inline_keyboard", []) or []:
                    for b in rr or []:
                        if getattr(b, "callback_data", None) == str(q.data):
                            label = str(getattr(b, "text", "") or "").strip()
                            break
            except Exception:
                pass
        if not label:
            await q.answer("این دکمه دیگر معتبر نیست؛ لطفاً منوی فعلی را باز کنید.", show_alert=True)
            raise ApplicationHandlerStop
        if row and row["user_id"] and str(row["user_id"]) != str(q.from_user.id):
            await q.answer("این گزینه برای کاربر دیگری است.", show_alert=True)
            raise ApplicationHandlerStop
        await q.answer()
        st = B.S.setdefault(q.from_user.id, {})
        if row and row["lang"]: st["lang"] = row["lang"]
        if row and row["status"]: st["status"] = row["status"]
        try:
            result = UI._dispatch(update, context, B, label)
            if inspect.isawaitable(result):
                await result
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("final callback failed label=%r", label)
            if st.get("partner_id") and st.get("partner_active") and not st.get("partner_logged_out"):
                await q.message.reply_text("❌ اجرای گزینه با خطای موقت روبه‌رو شد؛ پنل همکاران حفظ شد.", reply_markup=_partner_markup(B, q.from_user.id))
            else:
                await q.message.reply_text("❌ اجرای گزینه با خطای موقت روبه‌رو شد. لطفاً دوباره تلاش کنید.", reply_markup=B.main(q.from_user.id))
            raise ApplicationHandlerStop
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(callback, pattern=r"^ui2:"), group=-200000)
    B._final_service_owner_v28 = True
    log.info("Final Telegram partner service owner v28 installed: Irancell 980000")
