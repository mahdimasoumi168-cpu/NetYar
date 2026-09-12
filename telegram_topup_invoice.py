"""Clean partner top-up invoice with copyable card number."""
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
try:
    from telegram import CopyTextButton
except Exception:
    CopyTextButton = None


def _card(B):
    card=os.getenv("PAYMENT_CARD","").strip() or B.db.setting("card_number","").strip()
    owner=os.getenv("PAYMENT_CARD_OWNER","").strip() or B.db.setting("card_owner","فریبا خاوری").strip()
    return card,owner


def install(B):
    if getattr(B,"_topup_invoice_ui",False):return
    old_router=B.router
    async def router(update,context):
        uid=update.effective_user.id;st=B.S.setdefault(uid,{})
        if st.get("mode")!="topup_amount":return await old_router(update,context)
        raw=str(update.message.text or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
        raw=raw.replace(",","").replace("٬","").replace(" ","").replace("تومان","")
        if not raw.isdigit() or int(raw)<=0:return await update.message.reply_text("❌ مبلغ نامعتبر است. مثال: 500000",reply_markup=B.cancel_kb(st.get("lang","fa")))
        pid=st.get("partner_id");p=B.db.conn.execute("SELECT * FROM partners WHERE id=?",(pid,)).fetchone()
        if not p:return await update.message.reply_text("❌ حساب همکار پیدا نشد.",reply_markup=B.partner_kb(st.get("lang","fa")))
        amount=int(raw);st["mode"]="topup_receipt";st["topup_amount"]=amount;card,owner=_card(B)
        text=("🧾 <b>فاکتور شارژ حساب همکار</b>\n" "━━━━━━━━━━━━━━━━━━\n" f"👤 همکار: <b>{p['name']}</b>\n" f"💰 مبلغ شارژ: <b>{amount:,} تومان</b>\n" "━━━━━━━━━━━━━━━━━━\n" f"💳 شماره کارت:\n<code>{card or 'در تنظیمات پرداخت ثبت نشده است'}</code>\n" f"👤 به نام: <b>{owner or '-'}</b>\n" "━━━━━━━━━━━━━━━━━━\n" "📌 پس از واریز، روی «📸 ارسال رسید» بزنید و تصویر رسید را ارسال کنید.")
        rows=[]
        if card and CopyTextButton is not None:
            try:rows.append([InlineKeyboardButton("📋 کپی شماره کارت",copy_text=CopyTextButton(text=card))])
            except Exception:pass
        rows.append([InlineKeyboardButton("📸 ارسال رسید",callback_data="topupui:receipt")])
        rows.append([InlineKeyboardButton("❌ انصراف",callback_data="topupui:cancel")])
        return await update.message.reply_text(text,parse_mode="HTML",reply_markup=InlineKeyboardMarkup(rows))
    B.router=router

    from telegram.ext import CallbackQueryHandler
    async def callback(update,context):
        q=update.callback_query;data=str(q.data or "")
        if not data.startswith("topupui:"):return
        await q.answer();uid=q.from_user.id;st=B.S.setdefault(uid,{})
        if data=="topupui:cancel":
            st["mode"]=None
            return await q.message.reply_text("❌ عملیات لغو شد.",reply_markup=B.partner_kb(st.get("lang","fa")))
        if data=="topupui:receipt":
            st["mode"]="topup_receipt"
            return await q.message.reply_text("📸 تصویر رسید پرداخت را ارسال کنید.",reply_markup=B.cancel_kb(st.get("lang","fa")))

    B._topup_invoice_callback=callback
    B._topup_invoice_callback_handler=CallbackQueryHandler(callback,pattern=r"^topupui:")
    B._topup_invoice_install_app=lambda app:app.add_handler(B._topup_invoice_callback_handler,group=-12)
    B._topup_invoice_ui=True
