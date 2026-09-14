"""Complete Telegram request-details renderer with persisted request language."""
import logging
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop
log=logging.getLogger("netyar.telegram.request_details")


def _lang(B,rid):
 try:
  import request_language_actions as L
  return L.request_language(B.db,rid)
 except Exception:return "fa"

def _buttons(rid,lang):
 try:
  import request_language_actions as L
  return L.admin_markup(rid,lang,include_view=False)
 except Exception:
  return InlineKeyboardMarkup([[InlineKeyboardButton("📤 انتقال به آخر چت",callback_data=f"panel:resend:{rid}")]])

def _service(B,key,lang):
 try:
  import request_language_actions as L
  return L.service_name(key,lang)
 except Exception:return str(key or "-")

def _label(key,lang):
 try:
  import request_language_actions as L
  return L.field_label(key,lang)
 except Exception:return f"📋 {key}"

async def _show(update,context,B,rid):
 q=update.callback_query
 r=B.db.conn.execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
 if not r:
  await q.answer("درخواست پیدا نشد",show_alert=True); raise ApplicationHandlerStop
 if not B.admin(q.from_user.id):
  pid=B.S.get(q.from_user.id,{}).get("partner_id")
  if pid!=r["user_id"]: await q.answer("دسترسی ندارید",show_alert=True); raise ApplicationHandlerStop
 lang=_lang(B,rid)
 try:
  L=__import__("request_language_actions").labels(lang)
 except Exception:
  L={"details":"📋 جزئیات کامل درخواست","tracking":"🎫 کد پیگیری","service":"🧾 خدمت","status":"📌 وضعیت","amount":"💰 مبلغ","payment":"💳 وضعیت پرداخت","method":"💵 روش پرداخت","time":"🕐 زمان ثبت","info":"📋 اطلاعات ثبت‌شده","files":"📎 فایل پیوست دارد","none":"-"}
 answers=B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",(rid,)).fetchall()
 status=str(r["status"] or "-")
 lines=[L["details"],"",f"{L['tracking']}: {r['tracking_code']}",f"{L['service']}: {_service(B,r['service_key'],lang)}",f"{L['status']}: {status}",f"{L['amount']}: {int(r['amount'] or 0):,} Toman",f"{L['payment']}: {r['payment_status']}"]
 if r["payment_method"]: lines.append(f"{L['method']}: {r['payment_method']}")
 if r["created_at"]: lines.append(f"{L['time']}: {r['created_at']}")
 # Include every populated request-table field, not only the common fields.
 for key in r.keys():
  if key in {"id","tracking_code","service_key","status","amount","payment_status","payment_method","created_at","updated_at","language","user_id"}: continue
  value=str(r[key] or "").strip()
  if value: lines.append(f"{_label(key,lang)}: {value}")
 lines += ["",L["info"]]
 visible=0
 for a in answers:
  value=str(a["answer"] or "").strip(); has_file=bool(a["file_id"])
  if not value and not has_file: continue
  label=_label(a["field_key"],lang)
  lines.append(f"{label}: {value}" if value else f"{label}: {L['files']}"); visible+=1
 if not visible: lines.append(L["none"])
 # Remove the old "View Full Information" action from this view; the transfer
 # action is now the first/largest button.
 try: await q.message.edit_reply_markup(reply_markup=_buttons(rid,lang))
 except Exception: pass
 await q.message.reply_text("\n".join(lines),reply_markup=_buttons(rid,lang))
 for a in answers:
  fid=a["file_id"]
  if not fid: continue
  caption=_label(a["field_key"],lang)
  try:
   await q.message.reply_photo(photo=fid,caption=caption)
  except Exception:
   try: await q.message.reply_document(document=fid,caption=caption)
   except Exception: log.exception("request attachment delivery failed: request=%s field=%s",rid,a["field_key"])
 raise ApplicationHandlerStop

async def _callback(update,context,B):
 q=update.callback_query; data=str(q.data or "")
 if not data.startswith("panel:req:"): return
 try: rid=int(data.rsplit(":",1)[1])
 except Exception: await q.answer("Invalid request",show_alert=True); raise ApplicationHandlerStop
 await q.answer(); await _show(update,context,B,rid)

def install(app,B):
 if getattr(B,"_telegram_request_details_fix",False): return
 app.add_handler(CallbackQueryHandler(lambda u,c:_callback(u,c,B),pattern=r"^panel:req:"),group=-120)
 B._telegram_request_details_fix=True
