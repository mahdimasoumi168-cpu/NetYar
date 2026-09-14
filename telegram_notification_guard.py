"""Reliable Telegram notification owner with persisted per-request language."""
import asyncio, logging
log=logging.getLogger("netyar.telegram.notification_guard")

def _request_lang(B,request_id):
 try:
  import request_language_actions as L
  return L.request_language(B.db,request_id)
 except Exception:return "fa"

_LABELS={
 "en":{"🎫 کد پیگیری":"🎫 Tracking code","🎫 کد پیگیری:":"🎫 Tracking code:","🛠 خدمت":"🛠 Service","🛠 خدمت:":"🛠 Service:","📌 وضعیت":"📌 Status","📌 وضعیت:":"📌 Status:","💰 مبلغ":"💰 Amount","💰 مبلغ:":"💰 Amount:","💳 وضعیت پرداخت":"💳 Payment status","💳 وضعیت پرداخت:":"💳 Payment status:","💳 روش پرداخت":"💳 Payment method","👤 نام":"👤 Name","👤 نام:":"👤 Name:","📱 شماره":"📱 Phone","📱 شماره:":"📱 Phone:","🆕 درخواست جدید":"🆕 New request","🆕 درخواست خدمات ثبت شد":"🆕 Service request submitted","درخواست فیدای غیر حضوری":"FIDA online service request","درخواست فیدای غیرحضوری":"FIDA online service request","📋 درخواست شما ثبت شد.":"📋 Your request has been submitted.","از گزینه‌های زیر استفاده کنید:":"Use the options below:","📎 فایل":"📎 Files","📎 فایل:":"📎 Files:","تومان":"Toman","پرداخت شده":"Paid","در انتظار پرداخت":"Awaiting payment","در حال بررسی":"Under review","تأیید شده":"Approved","انجام شد":"Completed","رد شد":"Rejected"},
 "ar":{"🎫 کد پیگیری":"🎫 رمز التتبع","🎫 کد پیگیری:":"🎫 رمز التتبع:","🛠 خدمت":"🛠 الخدمة","🛠 خدمت:":"🛠 الخدمة:","📌 وضعیت":"📌 الحالة","📌 وضعیت:":"📌 الحالة:","💰 مبلغ":"💰 المبلغ","💰 مبلغ:":"💰 المبلغ","💳 وضعیت پرداخت":"💳 حالة الدفع","💳 وضعیت پرداخت:":"💳 حالة الدفع:","💳 روش پرداخت":"💳 طريقة الدفع","👤 نام":"👤 الاسم","👤 نام:":"👤 الاسم:","📱 شماره":"📱 الهاتف","📱 شماره:":"📱 الهاتف:","🆕 درخواست جدید":"🆕 طلب جديد","🆕 درخواست خدمات ثبت شد":"🆕 تم تسجيل طلب الخدمة","درخواست فیدای غیر حضوری":"طلب خدمة فيدا الإلكترونية","درخواست فیدای غیرحضوری":"طلب خدمة فيدا الإلكترونية","📋 درخواست شما ثبت شد.":"📋 تم تسجيل طلبكم.","از گزینه‌های زیر استفاده کنید:":"استخدموا الخيارات أدناه:","📎 فایل":"📎 الملفات","📎 فایل:":"📎 الملفات:","تومان":"تومان","پرداخت شده":"تم الدفع","در انتظار پرداخت":"بانتظار الدفع","در حال بررسی":"قيد المراجعة","تأیید شده":"تمت الموافقة","انجام شد":"تم الإنجاز","رد شد":"مرفوض"}
}

def _localize_text(text,lang):
 text=str(text or "")
 for src in sorted(_LABELS.get(lang,{}),key=len,reverse=True): text=text.replace(src,_LABELS[lang][src])
 return text

def _localized_markup(B,rid,lang):
 try:
  import request_language_actions as L
  return L.admin_markup(rid,lang)
 except Exception:
  from telegram import InlineKeyboardMarkup,InlineKeyboardButton
  names={"fa":("🔎 مشاهده کامل درخواست","⏳ در حال بررسی","✅ انجام شد","❌ رد درخواست","✉️ پاسخ به مشترک"),"en":("🔎 View Full Request","⏳ Under Review","✅ Completed","❌ Reject Request","✉️ Reply to Customer"),"ar":("🔎 عرض الطلب الكامل","⏳ قيد المراجعة","✅ تم الإنجاز","❌ رفض الطلب","✉️ الرد على المشترك")}[lang]
  return InlineKeyboardMarkup([[InlineKeyboardButton(names[0],callback_data=f"panel:req:{rid}")],[InlineKeyboardButton(names[1],callback_data=f"panel:review:{rid}"),InlineKeyboardButton(names[2],callback_data=f"panel:approve:{rid}")],[InlineKeyboardButton(names[3],callback_data=f"panel:reject:{rid}"),InlineKeyboardButton(names[4],callback_data=f"req:r:{rid}")]])

def install(app,B):
 if getattr(B,"_telegram_notification_guard",False): return
 async def notify_admins(application,message,request_id=None,inline=None,files=None):
  admins=list(getattr(B,"ADM",set()) or [])
  if not admins: log.warning("No Telegram admins configured; notification not sent"); return False
  lang=_request_lang(B,request_id) if request_id else "fa"
  localized=_localize_text(message,lang)
  markup=inline if inline is not None else (_localized_markup(B,request_id,lang) if request_id else None)
  ok=True; bot=application.bot
  for aid in admins:
   delivered=False
   for attempt in range(3):
    try: await bot.send_message(chat_id=int(aid),text=localized,reply_markup=markup); delivered=True; break
    except Exception:
     if attempt==2: log.exception("admin text notification failed: admin=%s request=%s",aid,request_id)
     else: await asyncio.sleep(.7*(attempt+1))
   for item in list(files or []):
    if not item: continue
    kind=str(item.get("type","photo")) if isinstance(item,dict) else "photo"; fid=item.get("file_id") if isinstance(item,dict) else str(item)
    if not fid: continue
    for attempt in range(3):
     try:
      if kind=="document": await bot.send_document(chat_id=int(aid),document=fid)
      else: await bot.send_photo(chat_id=int(aid),photo=fid)
      break
     except Exception:
      if attempt==2: log.exception("admin attachment notification failed: admin=%s request=%s",aid,request_id)
      else: await asyncio.sleep(.7*(attempt+1))
   if not delivered: ok=False
  return ok
 B.notify_admins=notify_admins; B._telegram_notification_guard=True
 log.info("Telegram notification guard installed with persisted request language")
