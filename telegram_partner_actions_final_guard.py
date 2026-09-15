"""Final Telegram partner-action callback guard."""
import logging
log=logging.getLogger("netyar.telegram.partner_actions_guard")
PARTNER="👥 پنل همکاران"
IRANCELL="📱 حل مشکل سیم کارت ایرانسل"
SIMBUY="📲 خرید سیم کارت"

def _partner_kb(B,uid):
    import telegram_ui_policy_v2 as UI
    return UI.inline([["➕ شارژ حساب","🏛 حل مشکل سامانه دولت من"],[IRANCELL,"🪪 فیدای غیر حضوری"],[SIMBUY,"🔎 پیگیری کد"],["📋 سوابق","💰 موجودی"],["🎫 تیکت به مدیریت"],["🚪 خروج از پنل"],["❌ انصراف"]],B,uid)

def install(app,B):
    if getattr(B,"_partner_actions_final_guard",False): return
    import telegram_ui_policy_v2 as UI
    old_dispatch=UI._dispatch
    def _logged_in(B,uid):
        st=B.S.setdefault(uid,{})
        pid=st.get("partner_id")
        if not pid or not st.get("partner_active",True): return False
        try:
            row=B.db.conn.execute("SELECT id FROM partners WHERE id=? AND active=1 LIMIT 1",(pid,)).fetchone()
            if not row: st.pop("partner_id",None);st.pop("partner_active",None);return False
        except Exception: log.exception("partner session validation failed");return False
        return True
    async def dispatch(update,context,bot,label):
        label=str(label or "").strip()
        aliases={"👥 Partner panel":PARTNER,"👥 لوحة الشركاء":PARTNER,"پنل همکاران":PARTNER,"📱 SIM services":IRANCELL}
        label=aliases.get(label,label)
        q=getattr(update,"callback_query",None);uid=q.from_user.id if q else update.effective_user.id;target=q.message if q else update.effective_message;st=B.S.setdefault(uid,{})
        if label==PARTNER:
            if not _logged_in(B,uid):
                st["mode"]="p_phone";st["step"]="partner_phone"
                return await target.reply_text("👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")))
            st["mode"]=None
            return await target.reply_text("👥 پنل همکاران\n\nیکی از خدمات زیر را انتخاب کنید:",reply_markup=_partner_kb(B,uid))
        if label==SIMBUY:
            if not _logged_in(B,uid):
                st["mode"]="p_phone";st["step"]="partner_phone"
                return await target.reply_text("❌ ابتدا وارد پنل همکاران شوید.",reply_markup=B.cancel_kb(st.get("lang","fa")))
            try:
                import telegram_sim_service as S
                return await S.start(B,uid,target)
            except Exception:
                log.exception("partner SIM purchase start failed")
                return await target.reply_text("❌ خدمت خرید سیم کارت فعلاً قابل اجرا نیست.",reply_markup=_partner_kb(B,uid))
        partner_actions={"➕ شارژ حساب","🏛 حل مشکل سامانه دولت من",IRANCELL,"🪪 فیدای غیر حضوری","🔎 پیگیری کد","📋 سوابق","💰 موجودی","🎫 تیکت به مدیریت"}
        if label in partner_actions and not _logged_in(B,uid):
            st["mode"]="p_phone";st["step"]="partner_phone"
            return await target.reply_text("❌ ابتدا وارد پنل همکاران شوید.\n\n📱 شماره موبایل اختصاصی همکار را وارد کنید:",reply_markup=B.cancel_kb(st.get("lang","fa")))
        try:return await old_dispatch(update,context,bot,label)
        except Exception:
            log.exception("partner action failed: %s",label);st["mode"]=None
            return await target.reply_text("❌ اجرای گزینه با خطا مواجه شد.\n\n👥 به پنل همکاران برگشتید.",reply_markup=_partner_kb(B,uid) if _logged_in(B,uid) else B.main(uid))
    UI._dispatch=dispatch
    B.partner_kb=lambda lang="fa":_partner_kb(B,UI._uid() or 0)
    B.partner_kb_for=lambda uid,lang="fa":_partner_kb(B,uid)
    B._partner_actions_final_guard=True
