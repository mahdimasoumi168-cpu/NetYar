"""Final Telegram state/UX hardening.

Keeps partner login as a two-step state machine, prevents legacy routers from
stealing the password step, and makes Cancel/restart return to the current UI.
"""
import logging

log = logging.getLogger("netyar.telegram_hardening")


def install():
    import bot as B
    import final_ui_flow_patch as F

    if getattr(B, "_telegram_final_hardening", False):
        return

    def _base_state(uid):
        old = B.S.get(uid, {}) or {}
        out = {"lang": old.get("lang", "fa")}
        if old.get("status"):
            out["status"] = old["status"]
        if old.get("partner_id"):
            out["partner_id"] = old.get("partner_id")
            out["partner_active"] = bool(old.get("partner_active", True))
        return out

    async def safe_cancel(update, context):
        uid = update.effective_user.id
        base = _base_state(uid)
        B.S[uid] = base
        if base.get("partner_id") and base.get("partner_active", True):
            markup = B.partner_kb(base.get("lang", "fa"))
        else:
            markup = B.main(uid)
        await update.message.reply_text(
            "❌ عملیات لغو شد.\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
            reply_markup=markup,
        )

    async def safe_partner(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        pid = st.get("partner_id")
        lang = st.get("lang", "fa")
        if pid and st.get("partner_active", True):
            p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1", (pid,)).fetchone()
            if p:
                st["mode"] = None
                return await update.message.reply_text(
                    f"👥 پنل همکاران\n👤 {p['name']}\n📱 {p['phone']}\n💰 {int(p['balance'] or 0):,} تومان",
                    reply_markup=B.partner_kb(lang),
                )
        B.S[uid] = {
            "lang": lang,
            "status": st.get("status", "foreign"),
            "mode": "p_phone",
        }
        await update.message.reply_text(
            "👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:",
            reply_markup=B.cancel_kb(lang),
        )

    async def safe_ptext(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        mode = st.get("mode")
        text = (getattr(update.message, "text", "") or "").strip()

        # STEP 1: phone lookup. Do not call the legacy router before this step.
        if mode == "p_phone":
            phone = B.normalize_phone(text)
            if not phone:
                return await update.message.reply_text(
                    "❌ شماره موبایل صحیح نیست.\nمثال: 09123456789\n\n📱 لطفاً دوباره شماره موبایل اختصاصی همکار را وارد کنید:",
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )
            p = B.db.partner(phone)
            if not p or not int(p["active"] or 0):
                return await update.message.reply_text(
                    "❌ همکار با این شماره پیدا نشد یا غیرفعال است.\n\n📱 شماره موبایل اختصاصی همکار را دوباره وارد کنید یا «❌ انصراف» را بزنید:",
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )
            st.update(phone=phone, mode="p_pass", pending_partner_id=int(p["id"]))
            return await update.message.reply_text(
                "🔐 رمز عبور پنل همکاران را وارد کنید:",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )

        # STEP 2: password verification. This was previously falling through
        # to the generic button router, producing «گزینه مدیریت شناخته نشد».
        if mode == "p_pass":
            phone = B.normalize_phone(st.get("phone", ""))
            p = B.db.partner(phone) if phone else None
            if not p or not int(p["active"] or 0) or not B.check_password(text, p["password_hash"]):
                return await update.message.reply_text(
                    "❌ شماره موبایل یا رمز عبور نادرست است.\n\n🔐 لطفاً رمز عبور پنل همکاران را دوباره وارد کنید:",
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )
            st.update(
                partner_id=int(p["id"]),
                partner_active=True,
                mode=None,
                pending_partner_id=None,
            )
            return await update.message.reply_text(
                f"✅ ورود با موفقیت انجام شد.\n\n👥 پنل همکاران\n👤 {p['name']}\n📱 {p['phone']}\n💰 اعتبار: {int(p['balance'] or 0):,} تومان",
                reply_markup=B.partner_kb(st.get("lang", "fa")),
            )

        return None

    B.cancel = safe_cancel
    B.partner = safe_partner
    B.ptext = safe_ptext

    old_ui_callback = F._ui_callback

    async def hardened_ui_callback(update, context):
        q = update.callback_query
        token = str(q.data or "")
        entry = F._UI.get(token)
        if not entry:
            return await old_ui_callback(update, context)
        _owner, label = entry
        label = str(label).strip()
        if label == "👥 پنل همکاران":
            await q.answer()
            fake = F._fixed_fake_update(update, label) if hasattr(F, "_fixed_fake_update") else F._fake_update(update, label)
            return await B.partner(fake, context)
        if label in {B.CANCEL, "❌ لغو", "Cancel", "إلغاء"}:
            await q.answer()
            fake = F._fixed_fake_update(update, label) if hasattr(F, "_fixed_fake_update") else F._fake_update(update, label)
            return await B.cancel(fake, context)
        return await old_ui_callback(update, context)

    F._ui_callback = hardened_ui_callback
    B._telegram_final_hardening = True
    log.info("FINAL Telegram partner login/state/cancel hardening installed")
