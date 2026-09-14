"""Universal Telegram partner-state owner.

Owns the two fragile paths that must never fall through to legacy routers:
partner phone/password authentication and direct communication with management.
"""
import logging
import re
from telegram.ext import MessageHandler, ApplicationHandlerStop, filters

log = logging.getLogger("netyar.telegram.universal_partner_guard")


def _phone(value):
    s = str(value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    s = re.sub(r"[\s\-()]+", "", s)
    if s.startswith("+98"): s = "0" + s[3:]
    elif s.startswith("0098"): s = "0" + s[4:]
    return s


def _partner(B, phone):
    """Resolve a partner using the same normalized lookup used by the main login.

    The old guard queried partners.phone=? directly, which caused the false
    'no active partner' error when an existing record was stored in legacy
    formats such as +98..., 0098..., Persian digits, spaces or dashes.
    """
    p = _phone(phone)
    if not re.fullmatch(r"09\d{9}", p):
        return None

    # Prefer the canonical DB method. telegram_partner_login_fix patches this
    # method with legacy-format normalization, so this path stays consistent
    # with the actual partner login implementation.
    try:
        resolver = getattr(B.db, "get_partner", None) or getattr(B.db, "partner", None)
        if callable(resolver):
            row = resolver(p)
            if row:
                return row
    except Exception:
        log.exception("canonical partner lookup failed")

    # Safe fallback for installations where the resolver has not been patched.
    try:
        row = B.db.conn.execute(
            "SELECT * FROM partners WHERE phone=? AND active=1 LIMIT 1", (p,)
        ).fetchone()
        if row:
            return row
        for candidate in B.db.conn.execute(
            "SELECT * FROM partners WHERE active=1 ORDER BY id DESC"
        ).fetchall():
            if _phone(candidate["phone"]) == p:
                return candidate
    except Exception:
        log.exception("partner lookup failed")
    return None


def _session(B, uid):
    st = B.S.get(uid, {}) or {}
    pid = st.get("partner_id")
    if not pid or st.get("partner_active") is False or st.get("partner_logged_out"):
        return None
    try:
        return B.db.conn.execute(
            "SELECT * FROM partners WHERE id=? AND active=1 LIMIT 1", (int(pid),)
        ).fetchone()
    except Exception:
        return None


def install(app, B):
    if getattr(B, "_universal_partner_guard", False):
        return

    async def text_owner(update, context):
        msg = getattr(update, "effective_message", None)
        user = getattr(update, "effective_user", None)
        if not msg or not user or not msg.text:
            return
        uid = user.id
        st = B.S.setdefault(uid, {})
        text = msg.text.strip()
        mode = st.get("mode")

        if text in {"👥 پنل همکاران", "🔵 👥 پنل همکاران", "پنل همکاران"}:
            p = _session(B, uid)
            if p:
                st.update(partner_phone=_phone(p["phone"]), partner_active=True, partner_logged_out=False, mode=None)
                await msg.reply_text(
                    f"👥 پنل همکاران\n👤 {p['name'] or '-'}\n📱 {p['phone']}\n💰 اعتبار قابل استفاده: {int(p['balance'] or 0):,} تومان\n\nگزینه موردنظر را انتخاب کنید:",
                    reply_markup=B.partner_kb(st.get("lang", "fa")),
                )
                raise ApplicationHandlerStop
            st.update(mode="p_phone", step="partner_phone", partner_logged_out=False)
            st.pop("pending_partner_id", None)
            await msg.reply_text(
                "👥 ورود به پنل همکاران\n\n📱 شماره موبایل اختصاصی همکار را وارد کنید:",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )
            raise ApplicationHandlerStop

        if mode in {"p_phone", "partner_phone"} or st.get("step") == "partner_phone":
            phone = _phone(text)
            if not re.fullmatch(r"09\d{9}", phone):
                st.update(mode="p_phone", step="partner_phone")
                await msg.reply_text(
                    "❌ شماره موبایل صحیح نیست.\n\n📱 شماره موبایل اختصاصی همکار را دوباره وارد کنید:",
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )
                raise ApplicationHandlerStop
            p = _partner(B, phone)
            if not p:
                st.update(mode="p_phone", step="partner_phone")
                await msg.reply_text(
                    "❌ این شماره به همکار فعال اختصاص ندارد.\n\n📱 شماره را دوباره وارد کنید:",
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )
                raise ApplicationHandlerStop
            st.update(
                phone=phone,
                partner_phone=phone,
                partner_id=int(p["id"]),
                partner_active=True,
                mode="p_pass",
                step="partner_pass",
                pending_partner_id=int(p["id"]),
            )
            await msg.reply_text("🔐 رمز عبور همکار را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            raise ApplicationHandlerStop

        if mode in {"p_pass", "partner_pass"} or st.get("step") == "partner_pass":
            phone = _phone(st.get("partner_phone") or st.get("phone"))
            p = _partner(B, phone)
            ok = False
            try:
                ok = bool(p and B.check_password(text, p["password_hash"]))
            except Exception:
                log.exception("partner password check failed")
            if not ok:
                st.update(mode="p_pass", step="partner_pass")
                await msg.reply_text(
                    "❌ رمز عبور نادرست است.\n\n🔐 رمز عبور همکار را دوباره وارد کنید:",
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )
                raise ApplicationHandlerStop
            st.update(
                partner=p["phone"],
                partner_phone=phone,
                partner_id=int(p["id"]),
                partner_active=True,
                partner_logged_out=False,
                mode=None,
                step="partner",
            )
            st.pop("pending_partner_id", None)
            try:
                B.db.set_setting(f"partner_chat_{p['id']}", str(uid))
                B.db.set_setting(f"partner_chat_{p['phone']}", str(uid))
            except Exception:
                log.exception("partner chat mapping failed")
            await msg.reply_text(
                f"✅ ورود با موفقیت انجام شد.\n\n👥 پنل همکاران\n👤 {p['name'] or '-'}\n📱 {p['phone']}\n💰 اعتبار قابل استفاده: {int(p['balance'] or 0):,} تومان\n\nگزینه موردنظر را انتخاب کنید:",
                reply_markup=B.partner_kb(st.get("lang", "fa")),
            )
            raise ApplicationHandlerStop

        if text == "💬 ارتباط با مدیریت":
            p = _session(B, uid) or _partner(B, st.get("partner_phone") or st.get("partner") or st.get("phone"))
            if not p:
                await msg.reply_text("⛔ ابتدا وارد پنل همکاران شوید.", reply_markup=B.main(uid))
                raise ApplicationHandlerStop
            st.update(
                partner_id=int(p["id"]),
                partner_phone=_phone(p["phone"]),
                partner_active=True,
                partner_logged_out=False,
                mode="final_partner_chat",
                final_chat_admin=None,
                final_chat_partner_id=int(p["id"]),
            )
            try:
                B.db.set_setting(f"partner_chat_{p['id']}", str(uid))
                B.db.set_setting(f"partner_chat_{p['phone']}", str(uid))
            except Exception:
                log.exception("management chat mapping failed")
            await msg.reply_text(
                "💬 ارتباط با مدیریت فعال شد.\n\nپیام، عکس، فایل، ویس یا ویدیو را ارسال کنید.\nبرای پایان ارتباط «❌ انصراف» را بزنید."
            )
            raise ApplicationHandlerStop

        if mode != "final_partner_chat":
            return
        p = _session(B, uid) or _partner(B, st.get("partner_phone") or st.get("partner") or st.get("phone"))
        if not p:
            st["mode"] = None
            await msg.reply_text("⛔ نشست همکار معتبر نیست. لطفاً دوباره وارد پنل شوید.", reply_markup=B.main(uid))
            raise ApplicationHandlerStop
        admins = list(getattr(B, "ADM", []) or [])
        if not admins:
            await msg.reply_text("❌ مدیریت در حال حاضر در دسترس نیست؛ نشست شما حفظ شد. لطفاً دوباره تلاش کنید.")
            raise ApplicationHandlerStop
        sent = 0
        header = f"💬 پیام همکار\n👤 {p['name'] or '-'}\n📱 {p['phone']}"
        for aid in admins:
            try:
                out = await context.bot.send_message(chat_id=int(aid), text=header + "\n\n" + text)
                B.db.set_setting(f"admin_reply_map_{out.message_id}", str(uid))
                sent += 1
            except Exception:
                log.exception("management text delivery failed")
        await msg.reply_text("✅ پیام برای مدیریت ارسال شد." if sent else "❌ ارسال پیام به مدیریت انجام نشد؛ نشست شما حفظ شد.")
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_owner), group=-20000)
    B._universal_partner_guard = True
    log.info("universal partner/login/management guard installed")
