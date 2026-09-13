"""Final Telegram session/contact/error guard.

Keeps authenticated partner sessions persistent until explicit logout, gives
partner->management chat a deterministic admin destination, and prevents a
normal router fall-through from being shown as an execution error.
"""
import os
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, MessageHandler, ApplicationHandlerStop, filters


def install(app, B):
    if getattr(B, "_final_user_state_guard_v1", False):
        return True

    # ---- Persistent partner session recovery -----------------------------
    try:
        import telegram_offhours_partner_gate_v2 as OFF
        old_active = OFF._active_partner_session

        def persistent_active(B0, uid):
            row = old_active(B0, uid)
            if row:
                return row
            try:
                # Recover from the durable Telegram<->partner link.
                row = B0.db.conn.execute(
                    "SELECT p.* FROM partners p JOIN partner_telegram_links l "
                    "ON l.partner_id=p.id WHERE l.telegram_user_id=? AND p.active=1 LIMIT 1",
                    (str(uid),),
                ).fetchone()
                if not row:
                    # Also recover from the chat mapping written at login.
                    rows = B0.db.conn.execute("SELECT * FROM partners WHERE active=1 ORDER BY id DESC").fetchall()
                    for p in rows:
                        for key in (f"partner_chat_{p['id']}", f"partner_chat_{p['phone']}"):
                            if str(B0.db.setting(key, "") or "").strip() == str(uid):
                                row = p
                                break
                        if row:
                            break
                if row:
                    st = B0.S.setdefault(uid, {})
                    st.update(
                        partner_id=int(row["id"]),
                        partner_phone=str(row["phone"] or ""),
                        partner=str(row["phone"] or ""),
                        partner_active=True,
                        partner_logged_out=False,
                        step="partner",
                    )
                    if not st.get("mode") or st.get("mode") in {"night_phone", "night_pass"}:
                        st["mode"] = "partner"
                    return row
            except Exception:
                return None
            return None

        OFF._active_partner_session = persistent_active

        def persistent_night_worker(B0, uid):
            row = persistent_active(B0, uid)
            if row:
                return True
            return False

        OFF.is_night_worker = persistent_night_worker
    except Exception:
        pass

    # ---- Normal UI router fall-through is not an error -------------------
    try:
        import telegram_ui_policy_v2 as UI
        old_dispatch = getattr(UI, "_dispatch", None)
        if old_dispatch and not getattr(UI, "_netyar_safe_dispatch_v1", False):
            async def safe_dispatch(update, context, B0, label):
                old_router = getattr(B0, "router", None)
                if old_router:
                    async def safe_router(*args, **kwargs):
                        result = await old_router(*args, **kwargs)
                        # None means: no legacy router claimed this button.
                        # It must not become a visible "not available" error.
                        return True if result is None else result
                    B0.router = safe_router
                try:
                    return await old_dispatch(update, context, B0, label)
                finally:
                    if old_router:
                        B0.router = old_router
            UI._dispatch = safe_dispatch
            UI._netyar_safe_dispatch_v1 = True
    except Exception:
        pass

    def admin_ids():
        out = []
        try:
            for x in getattr(B, "ADM", set()) or set():
                if str(x).strip().lstrip("-").isdigit():
                    out.append(int(x))
        except Exception:
            pass
        if not out:
            for x in os.getenv("ADMIN_IDS", "").replace(";", ",").split(","):
                if x.strip().lstrip("-").isdigit():
                    out.append(int(x))
        return list(dict.fromkeys(out))

    def resolve_admin(uid, pid=None):
        # Prefer the administrator previously associated with this partner.
        if pid:
            try:
                value = str(B.db.setting(f"final_chat_admin_{pid}", "") or "").strip()
                if value.lstrip("-").isdigit() and B.admin(int(value)):
                    return int(value)
            except Exception:
                pass
        ids = admin_ids()
        return ids[0] if ids else None

    def partner_row(uid):
        st = B.S.setdefault(uid, {})
        pid = st.get("partner_id")
        try:
            if pid:
                row = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)).fetchone()
                if row:
                    return row
            row = B.db.conn.execute(
                "SELECT p.* FROM partners p JOIN partner_telegram_links l ON l.partner_id=p.id "
                "WHERE l.telegram_user_id=? AND p.active=1 LIMIT 1", (str(uid),)
            ).fetchone()
            if row:
                st.update(partner_id=int(row["id"]), partner_phone=str(row["phone"] or ""), partner_active=True)
            return row
        except Exception:
            return None

    async def start_management(update, context):
        q = getattr(update, "callback_query", None)
        uid = int(q.from_user.id) if q else int(update.effective_user.id)
        row = partner_row(uid)
        if not row:
            target = q.message if q else update.effective_message
            await target.reply_text("⛔ ابتدا وارد پنل همکاران شوید.", reply_markup=B.main(uid))
            if q:
                raise ApplicationHandlerStop
            return
        pid = int(row["id"])
        admin = resolve_admin(uid, pid)
        if not admin:
            target = q.message if q else update.effective_message
            await target.reply_text("❌ مدیر سیستم برای ارتباط با مدیریت تنظیم نشده است.", reply_markup=B.partner_kb())
            if q:
                raise ApplicationHandlerStop
            return
        st = B.S.setdefault(uid, {})
        st.update(mode="final_partner_chat", partner_id=pid, partner_active=True,
                  final_chat_admin=int(admin), final_chat_partner_id=pid)
        st.pop("partner_logged_out", None)
        B.db.set_setting(f"final_chat_admin_{pid}", str(admin))
        try:
            B.db.set_setting(f"partner_chat_{pid}", str(uid))
            if row["phone"]:
                B.db.set_setting(f"partner_chat_{row['phone']}", str(uid))
        except Exception:
            pass
        target = q.message if q else update.effective_message
        await target.reply_text(
            "💬 ارتباط با مدیریت فعال شد.\n\nپیام، عکس، فایل، صوت یا ویس خود را ارسال کنید.\nبرای پایان ارتباط، «🚪 خروج از پنل» را بزنید.",
            reply_markup=B.partner_kb(),
        )
        try:
            await context.bot.send_message(
                chat_id=admin,
                text=f"💬 ارتباط با مدیریت\n👤 همکار: {row['name'] or '-'}\n📱 {row['phone'] or '-'}\n🆔 همکار: {pid}\n\nپیام‌های بعدی این همکار برای شما ارسال می‌شود.",
                reply_markup=B.amenu(),
            )
        except Exception:
            pass
        if q:
            try: await q.answer("ارتباط با مدیریت فعال شد")
            except Exception: pass
            raise ApplicationHandlerStop

    def callback_label(update):
        q = update.callback_query
        data = str(q.data or "")
        try:
            if data.startswith("ui2:"):
                row = B.db.conn.execute("SELECT label FROM ui2_callbacks WHERE token=? LIMIT 1", (data[4:],)).fetchone()
                return str(row["label"] or "") if row else ""
            if data.startswith("ik:"):
                from final_platform_fix import _actions
                return str(_actions.get(data, "") or "")
            if data.startswith("ui:"):
                from final_ui_flow_patch import _UI
                return str(_UI.get(data, (None, ""))[1] or "")
        except Exception:
            return ""
        return ""

    async def contact_callback(update, context):
        q = update.callback_query
        if not q:
            return
        label = callback_label(update).strip()
        if label not in {"💬 ارتباط با مدیریت", "✉️ تیکت به مدیریت", "💬 ارتباط با پشتیبانی"}:
            return
        await start_management(update, context)

    async def contact_text(update, context):
        msg = update.effective_message
        if not msg or not msg.text:
            return
        if str(msg.text).strip() != "💬 ارتباط با مدیریت":
            return
        await start_management(update, context)
        raise ApplicationHandlerStop

    # Must run before every legacy UI/callback owner.
    app.add_handler(CallbackQueryHandler(contact_callback), group=-70000)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, contact_text), group=-69999)
    B._final_user_state_guard_v1 = True
    return True
