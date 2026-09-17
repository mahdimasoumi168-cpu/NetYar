"""Final Telegram admin button/entry repair.

Runs last so later UI layers cannot remove the administrator entry from the
main reply keyboard. It also gives the button a high-priority direct handler.
"""
from telegram.ext import MessageHandler, filters, ApplicationHandlerStop

LABELS={"🛠 پنل مدیریت بات","🛠 پنل مدیریت","پنل مدیریت بات","پنل مدیریت"}

def install(app,B):
    if getattr(B,"_admin_button_final_v1",False):
        return
    old_main=getattr(B,"main",None)
    if callable(old_main):
        def main(uid):
            kb=old_main(uid)
            try:
                if not B.admin(uid):
                    return kb
                rows=[list(r) for r in kb.keyboard]
                if not any(any(str(x)=="🛠 پنل مدیریت بات" for x in row) for row in rows):
                    rows.insert(max(0,len(rows)-2),["🛠 پنل مدیریت بات"])
                    from telegram import ReplyKeyboardMarkup
                    return ReplyKeyboardMarkup(rows,resize_keyboard=True)
            except Exception:
                pass
            return kb
        B.main=main

    async def handler(update,context):
        m=update.effective_message; u=update.effective_user
        if not m or not u or (m.text or "").strip() not in LABELS or not B.admin(u.id):
            return
        try:
            import telegram_admin_plus as A
            menu=A._admin_menu()
        except Exception:
            menu=None
        await m.reply_text("🛠 پنل مدیریت کامل\n\nاز منوی زیر بخش موردنظر را انتخاب کنید:",reply_markup=menu)
        raise ApplicationHandlerStop

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handler),group=-30000)
    B._admin_button_final_v1=True
