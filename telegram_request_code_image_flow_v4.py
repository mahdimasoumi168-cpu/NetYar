"""Final request-code image relay; registered before generic media handlers."""
from telegram import InlineKeyboardMarkup,InlineKeyboardButton
from telegram.ext import CallbackQueryHandler,MessageHandler,filters,ApplicationHandlerStop

def puid(B,pid):
 try:
  r=B.db.conn.execute("SELECT telegram_user_id FROM partner_telegram_links WHERE partner_id=?",(pid,)).fetchone(); return int(r["telegram_user_id"]) if r and str(r["telegram_user_id"]).isdigit() else None
 except Exception:return None

def install(app,B):
 if getattr(B,"_rqcode_v4",False):return
 B.db.conn.execute("CREATE TABLE IF NOT EXISTS request_partner_code_images(request_id INTEGER PRIMARY KEY,admin_telegram_id INTEGER,partner_telegram_id INTEGER,file_id TEXT,created_at TEXT,code TEXT DEFAULT '')");B.db.conn.commit()
 async def ask(u,c):
  q=u.callback_query
  if not q or not B.admin(q.from_user.id):return
  p=q.data.split(":");
  if len(p)!=3:return
  rid=int(p[2]);r=B.db.conn.execute("SELECT user_id,tracking_code FROM requests WHERE id=?",(rid,)).fetchone()
  if not r:return
  target=puid(B,r["user_id"])
  if not target:await q.answer("تلگرام همکار متصل نیست",show_alert=True);return
  st=B.S.setdefault(q.from_user.id,{});st.update(rq4="admin_image",rq_rid=rid,rq_pid=r["user_id"])
  await q.answer();await q.message.reply_text(f"📸 تصویر مربوط به درخواست {r['tracking_code']} را همینجا ارسال کنید تا برای همکار همین درخواست فرستاده شود.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو",callback_data=f"rq4:cancel:{rid}")]]));raise ApplicationHandlerStop
 async def media(u,c):
  m=u.message;st=B.S.setdefault(u.effective_user.id,{})
  if st.get("rq4")!="admin_image":return
  rid=int(st["rq_rid"]);target=puid(B,st["rq_pid"]);f=m.photo[-1].file_id if m.photo else (m.document.file_id if m.document else "")
  if not f:return
  r=B.db.conn.execute("SELECT tracking_code FROM requests WHERE id=?",(rid,)).fetchone();tc=r["tracking_code"] if r else str(rid)
  B.db.conn.execute("INSERT OR REPLACE INTO request_partner_code_images(request_id,admin_telegram_id,partner_telegram_id,file_id,created_at,code) VALUES(?,?,?,?,?,?)",(rid,u.effective_user.id,target,f,B.now(),""));B.db.conn.commit()
  kb=InlineKeyboardMarkup([[InlineKeyboardButton("🔐 ارسال کد",callback_data=f"rq4:code:{rid}")]])
  try:
   if m.photo:await c.bot.send_photo(target,f,caption=f"📸 تصویر مدیریت\n🎫 {tc}\n\nپس از بررسی، «🔐 ارسال کد» را بزنید.",reply_markup=kb)
   else:await c.bot.send_document(target,f,caption=f"📸 تصویر مدیریت\n🎫 {tc}\n\nپس از بررسی، «🔐 ارسال کد» را بزنید.",reply_markup=kb)
  except Exception:await m.reply_text("❌ ارسال تصویر برای همکار انجام نشد.");raise ApplicationHandlerStop
  st["rq4"]=None;await m.reply_text("✅ تصویر برای همکار ارسال شد. کد او پس از ارسال مستقیماً به مدیریت می‌رسد.");raise ApplicationHandlerStop
 async def code(u,c):
  q=u.callback_query
  if not q:return
  p=q.data.split(":");
  if len(p)!=3:return
  rid=int(p[2]);r=B.db.conn.execute("SELECT partner_telegram_id,tracking_code FROM request_partner_code_images WHERE request_id=?",(rid,)).fetchone()
  if not r or int(r["partner_telegram_id"] or 0)!=q.from_user.id:return
  B.S.setdefault(q.from_user.id,{})["rq4"]="partner_code";B.S[q.from_user.id]["rq_rid"]=rid;await q.answer();await q.message.reply_text(f"🔐 کد درخواست {r['tracking_code']} را همینجا ارسال کنید:");raise ApplicationHandlerStop
 async def text(u,c):
  m=u.message;st=B.S.setdefault(u.effective_user.id,{})
  if st.get("rq4")!="partner_code":return
  rid=int(st["rq_rid"]);r=B.db.conn.execute("SELECT partner_telegram_id,tracking_code FROM request_partner_code_images WHERE request_id=?",(rid,)).fetchone();code=(m.text or "").strip()
  if not r or int(r["partner_telegram_id"] or 0)!=u.effective_user.id:return
  if not code:await m.reply_text("❌ کد را وارد کنید.");raise ApplicationHandlerStop
  B.db.conn.execute("UPDATE request_partner_code_images SET code=?,created_at=? WHERE request_id=?",(code,B.now(),rid));B.db.answer(rid,"partner_code",answer=code);B.db.conn.commit()
  for aid in B.ADM:
   try:await c.bot.send_message(int(aid),f"🔐 کد همکار دریافت شد\n🎫 {r['tracking_code']}\n🔢 کد: {code}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 مشاهده درخواست",callback_data=f"rq:detail:{rid}")]]))
   except Exception:pass
  st["rq4"]=None;await m.reply_text("✅ کد برای مدیریت ارسال شد.");raise ApplicationHandlerStop
 async def cancel(u,c):
  q=u.callback_query
  if not q or not B.admin(q.from_user.id):return
  B.S.setdefault(q.from_user.id,{})["rq4"]=None;await q.answer();await q.message.reply_text("❌ درخواست کد لغو شد.");raise ApplicationHandlerStop
 app.add_handler(CallbackQueryHandler(cancel,pattern=r"^rq4:cancel:"),group=-1000003)
 app.add_handler(CallbackQueryHandler(ask,pattern=r"^rq:ask:"),group=-1000002)
 app.add_handler(CallbackQueryHandler(code,pattern=r"^rq4:code:"),group=-1000002)
 app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,media),group=-1000002)
 app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text),group=-1000002)
 B._rqcode_v4=True
