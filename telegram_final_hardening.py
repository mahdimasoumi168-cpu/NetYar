"""Final Telegram state/UX hardening.

This is intentionally the last Telegram patch. It prevents stale state from
leaking between flows and keeps Cancel/Partner entry on the current UI.
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
            out["partner_id"] = old["partner_id"]
            out["partner_active"] = bool(old.get("partner_active", True))
        return out

    async def safe_cancel(update, context):
        uid = update.effective_user.id
        old = B.S.get(uid, {}) or {}
        base = _base_state(uid)
        B.S[uid] = base
        if base.get("partner_id") and base.get("partner_active", True):
            markup = B.partner_kb(base.get("lang", "fa"))
        else:
            markup = B.main(uid)
        await update.message.reply_text("❌ عملیات لغو شد.\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=markup)

    async def safe_partner(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        pid = st.get("partner_id")
        lang = st.get("lang", "fa")
        # A partner button always starts a clean login decision. Never let a
        # previous service/input mode fall through into the phone lookup.
        if pid and st.get("partner_active", True):
            p = B.db.conn.execute("SELECT * FROM partners WHERE id=?", (pid,)).fetchone()
            if p:
                st["mode"] = None
                return await update.message.reply_text(
                    f"👥 پنل همکاران\n👤 {p['name']}\n📱 {p['phone']}\n💰 اعتبار: {p['balance']:,} تومان",
                    reply_markup=B.partner_kb(lang),
                )
        B.S[uid] = {"lang": lang, "status": st.get("status", "foreign"), "mode": "p_phone"}
        await update.message.reply_text(
            "👥 ورود به پنل همکاران\n\n📱 لطفاً شماره همراه همکار را وارد کنید:",
            reply_markup=B.cancel_kb(lang),
        )

    async def safe_ptext(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        if st.get("mode") != "p_phone":
            return None
        t = B.normalize_phone(update.message.text)
        if not t:
            return await update.message.reply_text(
                "❌ شماره موبایل صحیح نیست.\nمثال: 09123456789\n\n📱 لطفاً دوباره شماره همراه همکار را وارد کنید:",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )
        p = B.db.partner(t)
        if not p:
            return await update.message.reply_text(
                "❌ همکار با این شماره پیدا نشد.\n\n📱 شماره همراه همکار را دوباره وارد کنید یا «❌ انصراف» را بزنید:",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )
        st.update(phone=t, mode="p_pass")
        return await update.message.reply_text(
            "🔐 رمز عبور پنل همکاران را وارد کنید:",
            reply_markup=B.cancel_kb(st.get("lang", "fa")),
        )

    B.cancel = safe_cancel
    B.partner = safe_partner
    B.ptext = safe_ptext

    # The inline callback layer must dispatch Partner and Cancel directly.
    # This avoids sending these two critical navigation actions through an
    # older text router that may still have a stale mode.
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
    log.info("FINAL Telegram state/cancel/partner hardening installed")
