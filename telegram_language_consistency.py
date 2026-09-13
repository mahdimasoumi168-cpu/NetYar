"""Canonical language lock for Telegram UI.

Keeps the language selected at startup authoritative for all canonical
main/partner keyboards. Legacy handlers may still use Persian internally,
but they are never allowed to replace the selected session language.
"""
from telegram import InlineKeyboardMarkup

TEXT={
 "fa":{"partner":"👥 پنل همکاران","admin":"🛠 پنل مدیریت بات","fida":"🪪 فیدای غیر حضوری","print":"🖨 خدمات چاپ","gov":"🪪 حل مشکل ورود اتباع دولت من","renew":"🎫 کد رهگیری تمدید کارت‌ها","sim":"📱 خدمات سیم کارت","screen":"📝 آزمون غربالگری","track":"🎫 پیگیری","wallet":"💰 کیف پول من","contact":"📞 تماس با ما","complaint":"📝 ثبت شکایت مشتریان","topup":"➕ شارژ حساب","pgov":"🏛 حل مشکل سامانه دولت من","ptrack":"🔎 پیگیری کد","history":"📋 سوابق","balance":"💰 موجودی","ticket":"🎫 تیکت به مدیریت","logout":"🚪 خروج از پنل","cancel":"❌ انصراف"},
 "en":{"partner":"👥 Partner panel","admin":"🛠 Admin panel","fida":"🪪 FIDA service","print":"🖨 Printing services","gov":"🪪 Government access help","renew":"🎫 Card renewal tracking","sim":"📱 SIM card services","screen":"📝 Screening test","track":"🎫 Track request","wallet":"💰 My wallet","contact":"📞 Contact us","complaint":"📝 Customer complaints","topup":"➕ Top up account","pgov":"🏛 Government access help","ptrack":"🔎 Track code","history":"📋 History","balance":"💰 Balance","ticket":"🎫 Ticket to admin","logout":"🚪 Exit panel","cancel":"❌ Cancel"},
 "ar":{"partner":"👥 لوحة الشركاء","admin":"🛠 لوحة الإدارة","fida":"🪪 خدمة فيدا","print":"🖨 خدمات الطباعة","gov":"🪪 مساعدة الدخول الحكومي","renew":"🎫 متابعة تجديد البطاقة","sim":"📱 خدمات شرائح الهاتف","screen":"📝 اختبار الفرز","track":"🎫 متابعة الطلب","wallet":"💰 محفظتي","contact":"📞 اتصل بنا","complaint":"📝 شكاوى العملاء","topup":"➕ شحن الحساب","pgov":"🏛 مساعدة الدخول الحكومي","ptrack":"🔎 متابعة الرمز","history":"📋 السجل","balance":"💰 الرصيد","ticket":"🎫 تذكرة للإدارة","logout":"🚪 خروج من اللوحة","cancel":"❌ إلغاء"}
}

FA={v:k for k,v in TEXT["fa"].items()}

def install(B):
    import telegram_ui_policy_v2 as UI
    old_dispatch=UI._dispatch
    def lang(uid):
        x=(B.S.get(uid,{}) or {}).get("lang","fa")
        return x if x in TEXT else "fa"
    def t(uid,key): return TEXT[lang(uid)][key]
    def main_rows(uid):
        if (B.S.get(uid,{}) or {}).get("status")=="iranian":
            rows=[["track","wallet"],["contact","complaint"]]
        else:
            rows=[["fida","print"],["gov","renew"],["sim","screen"],["track","wallet"],["contact","complaint"]]
        rows.append(["partner"])
        if B.admin(uid): rows.append(["admin"])
        return [[t(uid,k) for k in row] for row in rows]
    def partner_rows(uid):
        return [[t(uid,"topup"),t(uid,"pgov")],[t(uid,"ptrack"),t(uid,"history")],[t(uid,"balance"),t(uid,"ticket")],[t(uid,"logout")],[t(uid,"cancel")]]
    B.main=lambda uid:UI.inline(main_rows(uid),B,uid)
    B.partner_kb=lambda lang="fa":UI.inline(partner_rows(UI._uid() or 0),B,UI._uid() or 0)
    B.cancel_kb=lambda lang="fa":UI.inline([[t(UI._uid() or 0,"cancel")]],B,UI._uid() or 0)
    reverse={}
    for l,vals in TEXT.items():
        for key,value in vals.items(): reverse[value]=key
    async def dispatch(update,context,Bot,label):
        key=reverse.get(label)
        if key:
            canonical=FA[key]
            return await old_dispatch(update,context,Bot,canonical)
        return await old_dispatch(update,context,Bot,label)
    UI._dispatch=dispatch
    B._telegram_language_lock=True
