"""Deterministic request-code workflow.
Admin clicks request-code -> sends an image from that same admin account -> image is forwarded to the request's assigned partner -> partner sends one code -> management receives it tied to the same request.
"""
from telegram import InlineKeyboardMarkup,InlineKeyboardButton
from telegram.ext import CallbackQueryHandler,MessageHandler,filters,ApplicationHandlerStop

def partner_uid(B,pid):
 try:
  r=B.db.conn.execute("SELECT telegram_user_id FROM partner_telegram_links WHERE partner_id=?",(pid,)).fetchone(); return int(r["telegram_user_id"]) if r and str(r["telegram_user_id"]).isdigit() else None
 except Exception:return None

def install(app,B):
 if getattr(B,"_request_code_image_v3",False): return
 B.db.conn.execute("CREATE TABLE IF NOT EXISTS request_partner_code_images(request_id INTEGER PRIMARY KEY,admin_telegram_id INTEGER,partner_telegram_id INTEGER,file_id TEXT,created_at TEXT,code TEXT DEFAULT '')"); B.db.conn.commit()
 async def rqcb(u,c):
  q=u.callback_query
  if not q or not str(q.data or "").startswith("rq:"): return
  parts=q.data.split(":")
  if len(parts)!=3 or parts[1]!="ask" or not B.admin(q.from_user.id): return
  rid=int(parts[2]); r=B.db.conn.execute("SELECT user_id,tracking_code FROM requests WHERE id=?",(rid,)).fetchone()
  if not r: await q.answer("درخواست پیدا نشد",show_alert=True); return
  target=partner_uid(B,r["user_id"])
  if not target: await q.answer("تلگرام همکار برای این درخواست متصل نیست",show_alert=True); return
  st=B.S.setdefault(q.from_user.id,{})
  st.update(rqcode_mode="wait_admin_image",rqcode_request_id=rid,rqcode_partner_id=r["user_id"],rqcode_admin_id=q.from_user.id)
  await q.answer(); await q.message.reply_text(f"📸 تصویر مربوط به درخواست {r['tracking_code']} را همینجا ارسال کنید.\n\nتصویر مستقیماً برای همکار همین درخواست ارسال می‌شود.",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ لغو",callback_data=f"rqcode:cancel:{rid}")]])); raise ApplicationHandlerStop
 async def admin_media(u,c):
  m=u.message; st=B.S.setdefault(u.effective_user.id,{})
  if st.get("rqcode_mode")!="wait_admin_image": return
  if not (m.photo or m.document): await m.reply_text("❌ لطفاً تصویر را ارسال کنید."); raise ApplicationHandlerStop
  rid=int(st["rqcode_request_id"]); pid=st["rqcode_partner_id"]; target=partner_uid(B,pid)
  if not target: await m.reply_text("❌ همکار این درخواست دیگر متصل نیست."); raise ApplicationHandlerStop
  f=m.photo[-1].file_id if m.photo else m.document.file_id; r=B.db.conn.execute("SELECT tracking_code FROM requests WHERE id=?",(rid,)).fetchone(); code=r["tracking_code"] if r else str(rid)
  B.db.conn.execute("INSERT OR REPLACE INTO request_partner_code_images(request_id,admin_telegram_id,partner_telegram_id,file_id,created_at,code) VALUES(?,?,?,?,?,?)",(rid,u.effective_user.id,target,f,B.now(),"")); B.db.conn.commit()
  kb=InlineKeyboardMarkup([[InlineKeyboardButton("🔐 ارسال کد",callback_data=f"rqcode3:send:{rid}")]])
  try:
   if m.photo: await c.bot.send_photo(target,f,caption=f"📸 تصویر درخواست مدیریت\n🎫 {code}\n\nپس از بررسی، دکمه «🔐 ارسال کد» را بزنید و کد را همینجا بفرستید.",reply_markup=kb)
   else: await c.bot.send_document(target,f,caption=f"📸 تصویر درخواست مدیریت\n🎫 {code}\n\nپس از بررسی، دکمه «🔐 ارسال کد» را بزنید و کد را همینجا بفرستید.",reply_markup=kb)
  except Exception: await m.reply_text("❌ ارسال تصویر برای همکار انجام نشد."); raise ApplicationHandlerStop
  st["rqcode_mode"]=None; await m.reply_text("✅ تصویر برای همکار ارسال شد.\nکد همکار پس از ارسال مستقیم برای مدیریت می‌آید."); raise ApplicationHandlerStop
 async def codecb(u,c):
  q=u.callback_query
  if not q or not str(q.data or "").startswith("rqcode3:"): return
  p=q.data.split(":")
  if len(p)!=3:return
  rid=int(p[2]); row=B.db.conn.execute("SELECT partner_telegram_id,tracking_code FROM request_partner_code_images WHERE request_id=?",(rid,)).fetchone()
  if not row or int(row["partner_telegram_id"] or 0)!=q.from_user.id: await q.answer("این درخواست برای شما نیست",show_alert=True); return
  if p[1]!="send":return
  B.S.setdefault(q.from_user.id,{})["rqcode_mode"]="wait_partner_code"; B.S[q.from_user.id]["rqcode_request_id"]=rid; await q.answer(); await q.message.reply_text(f"🔐 کد درخواست {row['tracking_code']} را همینجا ارسال کنید:"); raise ApplicationHandlerStop
 async def codetext(u,c):
  m=u.message; st=B.S.setdefault(u.effective_user.id,{})
  if st.get("rqcode_mode")!="wait_partner_code": return
  rid=int(st["rqcode_request_id"]); row=B.db.conn.execute("SELECT partner_telegram_id,tracking_code FROM request_partner_code_images WHERE request_id=?",(rid,)).fetchone()
  if not row or int(row["partner_telegram_id"] or 0)!=u.effective_user.id:return
  code=(m.text or "").strip()
  if not code: await m.reply_text("❌ کد را وارد کنید."); raise ApplicationHandlerStop
  B.db.conn.execute("UPDATE request_partner_code_images SET code=?,created_at=? WHERE request_id=?",(code,B.now(),rid)); B.db.answer(rid,"partner_code",answer=code); B.db.conn.commit()
  for aid in B.ADM:
   try: await c.bot.send_message(int(aid),f"🔐 کد همکار دریافت شد\n🎫 {row['tracking_code']}\n👤 همکار: {u.effective_user.full_name or u.effective_user.id}\n🔢 کد: {code}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔎 مشاهده درخواست",callback_data=f"rq:detail:{rid}")]]))
   except Exception: pass
  st["rqcode_mode"]=None; await m.reply_text("✅ کد برای مدیریت ارسال شد."); raise ApplicationHandlerStop
 async def cancel(u,c):
  q=u.callback_query
  if not q or not str(q.data or "").startswith("rqcode:cancel:") or not B.admin(q.from_user.id):return
  B.S.setdefault(q.from_user.id,{})["rqcode_mode"]=None; await q.answer(); await q.message.reply_text("❌ درخواست کد لغو شد."); raise ApplicationHandlerStop
 app.add_handler(CallbackQueryHandler(cancel,pattern=r"^rqcode:cancel:"),group=-1000001)
 app.add_handler(CallbackQueryHandler(rqcb,pattern=r"^rq:ask:"),group=-1000000)
 app.add_handler(CallbackQueryHandler(codecb,pattern=r"^rqcode3:"),group=-1000000)
 app.add_handler(MessageHandler(filters.PHOTO|filters.Document.ALL,admin_media),group=-1000000)
 app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,codetext),group=-1000000)
 B._request_code_image_v3=True
