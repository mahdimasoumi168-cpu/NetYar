"""Final canonical partner router v29.
This layer is installed last and also wraps telegram_ui_policy_v2._dispatch,
so legacy captured dispatch chains cannot bypass the final partner routes.
"""
import inspect
import logging
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.partner_final_router_v29")
IRANCELL = "📱 حل مشکل سیم کارت ایرانسل"
MANAGEMENT = "💬 ارتباط با مدیریت"
SIM_SERVICE = "📱 خدمات سیم کارت"
CANCEL = "❌ انصراف"
PRICE = 980_000


def _menu(B, uid):
    import telegram_ui_policy_v2 as UI
    return UI.inline([
        ["➕ شارژ حساب", IRANCELL],
        ["🏛 حل مشکل سامانه دولت من", "🎫 درخواست‌های من"],
        [SIM_SERVICE, "🪪 فیدای غیر حضوری"],
        ["🔎 پیگیری کد", "📋 سوابق"],
        ["💰 موجودی"],
        ["🎫 تیکت به مدیریت", MANAGEMENT],
        ["🚪 خروج از پنل"],
        [CANCEL],
    ], B, uid)


def _admin(B):
    for attr in ("ADM", "ADMINS"):
        vals = getattr(B, attr, ()) or ()
        if isinstance(vals, (str, int)):
            vals = (vals,)
        for value in vals:
            try:
                return int(value)
            except Exception:
                pass
    return None


async def _management(update, context, B, st):
    q = update.callback_query
    uid = q.from_user.id
    pid = st.get("partner_id")
    if not pid or not st.get("partner_active") or st.get("partner_logged_out"):
        await q.message.reply_text("⛔ ابتدا وارد پنل همکاران شوید.", reply_markup=B.main(uid))
        raise ApplicationHandlerStop
    row = B.db.conn.execute("SELECT id,name,phone FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)).fetchone()
    if not row:
        st.update(partner_active=False, mode=None, partner_logged_out=True)
        st.pop("partner_id", None)
        await q.message.reply_text("⛔ حساب همکار فعال نیست. لطفاً دوباره وارد شوید.", reply_markup=B.main(uid))
        raise ApplicationHandlerStop
    aid = _admin(B)
    if not aid:
        await q.message.reply_text("❌ مدیر برای ارتباط با مدیریت تنظیم نشده است.", reply_markup=_menu(B, uid))
        raise ApplicationHandlerStop
    try:
        B.db.set_setting(f"partner_chat_{int(pid)}", str(uid))
        if row["phone"]:
            B.db.set_setting(f"partner_chat_{row['phone']}", str(uid))
        B.db.set_setting(f"final_chat_admin_{int(pid)}", str(aid))
    except Exception:
        log.exception("management mapping failed")
    st.update(mode="final_partner_chat", final_chat_admin=int(aid), final_chat_partner_id=int(pid), chat_reply_pending=False)
    try:
        await context.bot.send_message(chat_id=aid, text=(
            f"💬 ارتباط با مدیریت از طرف همکار فعال شد.\n\n"
            f"👤 همکار: {row['name'] or '-'}\n📱 شماره همکار: {row['phone'] or '-'}\n"
            f"🆔 شناسه همکار: {int(pid)}\n\nپیام، عکس، فایل، ویس یا ویدیو همکار برای شما ارسال می‌شود."
        ))
    except Exception:
        log.exception("management notification failed")
    await q.message.reply_text(
        "💬 ارتباط با مدیریت فعال شد.\n\nحالا پیام، عکس، فایل، ویس یا ویدیو را ارسال کنید.\nبرای پایان، «❌ انصراف» را بزنید.",
        reply_markup=B.cancel_kb(st.get("lang", "fa")),
    )
    raise ApplicationHandlerStop


async def _irancell(update, context, B, st):
    q = update.callback_query
    uid = q.from_user.id
    pid = st.get("partner_id")
    if not pid or not st.get("partner_active") or st.get("partner_logged_out"):
        await q.message.reply_text("⛔ ابتدا وارد پنل همکاران شوید.", reply_markup=B.main(uid))
        raise ApplicationHandlerStop
    try:
        import telegram_irancell_partner_service as IRS
        IRS.PRICE = PRICE
        IRS._ensure_service(B)
        B.db.conn.execute("UPDATE services SET price=?, active=1 WHERE key=?", (PRICE, "irancell_sim_issue"))
        B.db.conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", ("price_irancell_sim", str(PRICE)))
        B.db.conn.commit()
    except Exception:
        try: B.db.conn.rollback()
        except Exception: pass
        log.exception("Irancell registration failed")
    st["mode"] = "irancell_partner_phone"
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


async def _sim_service(update, context, B, st):
    q = update.callback_query
    fn = getattr(B, "sim_start", None)
    if fn:
        import telegram_ui_policy_v2 as UI
        fake = UI._fake(update, SIM_SERVICE)
        result = fn(fake, context)
        if inspect.isawaitable(result):
            await result
        raise ApplicationHandlerStop
    await q.message.reply_text("📱 خدمات سیم کارت\n\nاین خدمت در حال حاضر برای پنل همکاران فعال نشده است.", reply_markup=_menu(B, q.from_user.id))
    raise ApplicationHandlerStop


def install(app, B):
    if getattr(B, "_partner_final_router_v29", False):
        return
    import telegram_ui_policy_v2 as UI
    UI.MANAGEMENT = MANAGEMENT
    UI.IRANCELL = IRANCELL

    # Critical fix: old modules captured UI._dispatch before v29 was loaded.
    # Replace it now so even those stale wrappers cannot reach the broken
    # NameError path in telegram_ui_policy_v2.
    old_dispatch = UI._dispatch

    async def final_dispatch(update, context, bot, label):
        label = str(label or "").strip()
        q = getattr(update, "callback_query", None)
        if q:
            uid = q.from_user.id
            st = bot.S.setdefault(uid, {})
            if label == IRANCELL:
                return await _irancell(update, context, bot, st)
            if label == MANAGEMENT:
                return await _management(update, context, bot, st)
            if label == SIM_SERVICE:
                return await _sim_service(update, context, bot, st)
        result = old_dispatch(update, context, bot, label)
        if inspect.isawaitable(result):
            return await result
        return result

    UI._dispatch = final_dispatch
    UI._final_partner_router_v29_dispatch = True

    B.partner_kb = lambda lang="fa": _menu(B, int(UI._uid() or 0))
    B._partner_service_price = PRICE

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
                    for button in rr or []:
                        if getattr(button, "callback_data", None) == str(q.data):
                            label = str(getattr(button, "text", "") or "").strip(); break
            except Exception:
                pass
        if not label:
            await q.answer("این دکمه دیگر معتبر نیست؛ لطفاً پنل همکاران را دوباره باز کنید.", show_alert=True)
            raise ApplicationHandlerStop
        await q.answer()
        st = B.S.setdefault(q.from_user.id, {})
        if row and row["lang"]: st["lang"] = row["lang"]
        if row and row["status"]: st["status"] = row["status"]
        try:
            result = final_dispatch(update, context, B, label)
            if inspect.isawaitable(result):
                await result
        except ApplicationHandlerStop:
            raise
        except Exception:
            log.exception("v29 callback failed label=%r", label)
            if st.get("partner_id") and st.get("partner_active") and not st.get("partner_logged_out"):
                await q.message.reply_text("❌ خطای موقت در اجرای گزینه؛ پنل همکاران حفظ شد.", reply_markup=_menu(B, q.from_user.id))
            else:
                await q.message.reply_text("❌ لطفاً دوباره تلاش کنید.", reply_markup=B.main(q.from_user.id))
            raise ApplicationHandlerStop
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(callback, pattern=r"^ui2:"), group=-1000000)
    B._partner_final_router_v29 = True
    log.info("FINAL partner router v29 installed: canonical dispatch + Irancell 980000 + management + SIM service")
