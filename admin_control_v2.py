"""Final admin/UI corrections layered after full_admin_control_patch."""
import logging
log = logging.getLogger("netyar.admin_v2")

MENU_ITEMS = {
    "fida": ("🪪 فیدای غیر حضوری", "🪪 FIDA service", "🪪 خدمة فيدا"),
    "print": ("🖨 خدمات چاپ", "🖨 Printing", "🖨 الطباعة"),
    "government": ("🏛 حل مشکل ورود اتباع دولت من", "🏛 Government access", "🏛 خدمات الحكومة"),
    "screening": ("📝 آزمون غربالگری", "📝 Screening test", "📝 اختبار الفحص"),
    "tracking": ("🎫 پیگیری", "🎫 Follow-up", "🎫 متابعة"),
    "wallet": ("💰 کیف پول من", "💰 My wallet", "💰 محفظتي"),
    "contact": ("📞 تماس با ما", "📞 Contact us", "📞 اتصل بنا"),
    "complaint": ("📝 ثبت شکایت مشتریان", "📝 Customer complaint", "📝 شكوى العميل"),
    "partner": ("🔵 👥 پنل همکاران", "🔵 👥 Partner panel", "🔵 👥 لوحة الشركاء"),
}


def install():
    import bot as B
    if getattr(B, "_admin_v2_installed", False):
        return

    old_main = B.main
    def main(uid):
        markup = old_main(uid)
        try:
            lang = B.S.get(uid, {}).get("lang", "fa")
            source = getattr(markup, "inline_keyboard", None) or getattr(markup, "keyboard", None)
            if source is None:
                return markup
            out_rows=[]
            for row in source:
                out=[]
                for btn in row:
                    text=getattr(btn, "text", str(btn))
                    matched=None
                    for key, labels in MENU_ITEMS.items():
                        if text in labels:
                            matched=key; break
                    if matched and B.db.setting("menu_"+matched+"_active", "1") != "1":
                        continue
                    # Editable label for the current language.
                    if matched:
                        custom=B.db.setting("label_"+matched+"_"+lang, "")
                        if custom:
                            try:
                                from telegram import InlineKeyboardButton
                                cb=getattr(btn, "callback_data", None)
                                out.append(InlineKeyboardButton(custom, callback_data=cb, style=getattr(btn,"style",None)))
                                continue
                            except Exception:
                                pass
                    out.append(btn)
                if out: out_rows.append(out)
            if hasattr(markup, "inline_keyboard"):
                from telegram import InlineKeyboardMarkup
                return InlineKeyboardMarkup(out_rows)
            return B.kb([[getattr(x,"text",str(x)) for x in r] for r in out_rows])
        except Exception:
            log.exception("admin v2 menu filter failed")
            return markup
    B.main = main

    old_router = B.router
    async def router(update, context):
        uid=update.effective_user.id
        text=(getattr(update.message,"text","") or "").strip()
        if B.admin(uid):
            st=B.S.setdefault(uid,{})
            mode=st.get("admin_mode")
            if text=="🔧 مدیریت خدمات":
                st["admin_mode"]="menu_services"
                rows=[]
                for key,labels in MENU_ITEMS.items():
                    state=B.db.setting("menu_"+key+"_active","1")
                    rows.append([("🟢 " if state=="1" else "🔴 ")+key])
                rows.append(["⬅️ بازگشت"])
                return await update.message.reply_text("🔧 باز/بسته کردن تک‌تک گزینه‌های منو:",reply_markup=B.kb(rows))
            if mode=="menu_services":
                key=text.replace("🟢 ","").replace("🔴 ","").strip()
                if key in MENU_ITEMS:
                    cur=B.db.setting("menu_"+key+"_active","1");new="0" if cur=="1" else "1"
                    B.db.set_setting("menu_"+key+"_active",new)
                    return await update.message.reply_text(("🟢 باز شد: " if new=="1" else "🔴 بسته شد: ")+key,reply_markup=B.kb([["🔧 مدیریت خدمات"],["⬅️ بازگشت"]]))
            if text=="📝 مدیریت متن‌ها":
                st["admin_mode"]="texts_v2"
                return await update.message.reply_text("📝 متن موردنظر را انتخاب کنید:",reply_markup=B.kb([["welcome_fa","welcome_en"],["welcome_ar","contact_text"],["⬅️ بازگشت"]]))
            if mode=="texts_v2" and text in {"welcome_fa","welcome_en","welcome_ar","contact_text"}:
                st["text_key"]=text;st["admin_mode"]="text_value_v2"
                return await update.message.reply_text("✏️ متن جدید را ارسال کنید:",reply_markup=B.kb([["⬅️ بازگشت"]]))
            if mode=="text_value_v2":
                B.db.set_setting(st.get("text_key"),text);st["admin_mode"]="texts_v2"
                return await update.message.reply_text("✅ متن ذخیره شد.",reply_markup=B.kb([["welcome_fa","welcome_en"],["welcome_ar","contact_text"],["⬅️ بازگشت"]]))
        # Support is available to every user and uses the editable admin text.
        if text in {"📞 تماس با ما","📞 Contact us","📞 اتصل بنا"}:
            msg=B.db.setting("contact_text", "📞 پشتیبانی\n\nبرای ارتباط با پشتیبانی به این آیدی پیام دهید:\n@Good_ok_2000")
            return await update.message.reply_text(msg,reply_markup=B.main(uid))
        return await old_router(update, context)
    B.router = router

    # Language prompts are localized from the selected language and never fall
    # back to the old Iranian-disabled message.
    old_lang = B.langcb
    async def langcb(update, context):
        q=update.callback_query; await q.answer(); uid=q.from_user.id; lang=str(q.data).split(":",1)[-1]
        B.S[uid]={"lang":lang}
        texts={"fa":"آیا اتباع هستید یا ایرانی؟","en":"Are you a foreign citizen or Iranian?","ar":"هل أنت من اتباع أم إيراني؟"}
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        return await q.message.reply_text(texts.get(lang,texts["fa"]),reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪪 اتباع هستم",callback_data="st:foreign"),InlineKeyboardButton("🇮🇷 ایرانی هستم",callback_data="st:iranian")]]))
    B.langcb = langcb

    B._admin_v2_installed=True
    log.info("admin control v2 installed")
