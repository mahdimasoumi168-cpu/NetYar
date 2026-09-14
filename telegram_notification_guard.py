"""Reliable Telegram notification owner with per-request language localization."""
import asyncio
import logging

log = logging.getLogger("netyar.telegram.notification_guard")


def _request_lang(B, request_id):
    """Resolve the language selected by the user who owns this request."""
    try:
        r = B.db.conn.execute("SELECT user_id,platform FROM requests WHERE id=?", (request_id,)).fetchone()
        if not r:
            return "fa"
        u = B.db.conn.execute("SELECT external_id,platform FROM users WHERE id=?", (r["user_id"],)).fetchone()
        if not u:
            return "fa"
        ext = str(u["external_id"] or "")
        if str(r["platform"] or u["platform"] or "").lower() == "rubika":
            try:
                import rubika_v2 as R
                return str(R.STATE.get(ext, {}).get("lang", "fa")) if str(R.STATE.get(ext, {}).get("lang", "fa")) in {"fa", "en", "ar"} else "fa"
            except Exception:
                return "fa"
        st = getattr(B, "S", {}).get(int(ext), {}) if ext.isdigit() else {}
        value = str(st.get("lang", "fa"))
        return value if value in {"fa", "en", "ar"} else "fa"
    except Exception:
        return "fa"


_LABELS = {
    "en": {
        "🎫 کد پیگیری": "🎫 Tracking code", "🎫 کد پیگیری:": "🎫 Tracking code:",
        "🎫 کد": "🎫 Code", "🛠 خدمت": "🛠 Service", "🛠 خدمت:": "🛠 Service:",
        "📌 وضعیت": "📌 Status", "📌 وضعیت:": "📌 Status:", "💰 مبلغ": "💰 Amount",
        "💰 مبلغ:": "💰 Amount:", "💳 وضعیت پرداخت": "💳 Payment status",
        "💳 وضعیت پرداخت:": "💳 Payment status:", "💳 روش پرداخت": "💳 Payment method",
        "👤 نام": "👤 Name", "👤 نام:": "👤 Name:", "📱 شماره": "📱 Phone",
        "📱 شماره:": "📱 Phone:", "🕐 تاریخ ثبت": "🕐 Created at", "🕐 آخرین تغییر": "🕐 Last updated",
        "👤 شناسه کاربر": "👤 User ID", "👤 شناسه روبیکا": "👤 Rubika ID",
        "🆕 درخواست جدید": "🆕 New request", "🆕 درخواست خدمات ثبت شد": "🆕 Service request submitted",
        "درخواست فیدای غیر حضوری": "FIDA online service request", "درخواست فیدای غیرحضوری": "FIDA online service request",
        "📋 درخواست شما ثبت شد.": "📋 Your request has been submitted.",
        "از گزینه‌های زیر استفاده کنید:": "Use the options below:",
        "📎 فایل": "📎 Files", "📎 فایل:": "📎 Files:",
        "💰": "💰", "تومان": "Toman", "پرداخت شده": "Paid", "در انتظار پرداخت": "Awaiting payment",
        "در حال بررسی": "Under review", "تأیید شده": "Approved", "انجام شد": "Completed", "رد شد": "Rejected",
    },
    "ar": {
        "🎫 کد پیگیری": "🎫 رمز التتبع", "🎫 کد پیگیری:": "🎫 رمز التتبع:",
        "🎫 کد": "🎫 الرمز", "🛠 خدمت": "🛠 الخدمة", "🛠 خدمت:": "🛠 الخدمة:",
        "📌 وضعیت": "📌 الحالة", "📌 وضعیت:": "📌 الحالة:", "💰 مبلغ": "💰 المبلغ",
        "💰 مبلغ:": "💰 المبلغ:", "💳 وضعیت پرداخت": "💳 حالة الدفع",
        "💳 وضعیت پرداخت:": "💳 حالة الدفع:", "💳 روش پرداخت": "💳 طريقة الدفع",
        "👤 نام": "👤 الاسم", "👤 نام:": "👤 الاسم:", "📱 شماره": "📱 الهاتف",
        "📱 شماره:": "📱 الهاتف:", "🕐 تاریخ ثبت": "🕐 تاريخ التسجيل", "🕐 آخرین تغییر": "🕐 آخر تحديث",
        "👤 شناسه کاربر": "👤 معرّف المستخدم", "👤 شناسه روبیکا": "👤 معرّف روبیکا",
        "🆕 درخواست جدید": "🆕 طلب جديد", "🆕 درخواست خدمات ثبت شد": "🆕 تم تسجيل طلب الخدمة",
        "درخواست فیدای غیر حضوری": "طلب خدمة فيدا الإلكترونية", "درخواست فیدای غیرحضوری": "طلب خدمة فيدا الإلكترونية",
        "📋 درخواست شما ثبت شد.": "📋 تم تسجيل طلبكم.",
        "از گزینه‌های زیر استفاده کنید:": "استخدموا الخيارات أدناه:",
        "📎 فایل": "📎 الملفات", "📎 فایل:": "📎 الملفات:",
        "تومان": "تومان", "پرداخت شده": "تم الدفع", "در انتظار پرداخت": "بانتظار الدفع",
        "در حال بررسی": "قيد المراجعة", "تأیید شده": "تمت الموافقة", "انجام شد": "تم الإنجاز", "رد شد": "مرفوض",
    },
}


def _localize_text(text, lang):
    text = str(text or "")
    if lang == "fa":
        return text
    # Long phrases first, then field labels. Values such as names, codes and
    # uploaded-document text are deliberately preserved verbatim.
    mapping = _LABELS.get(lang, {})
    for src in sorted(mapping, key=len, reverse=True):
        text = text.replace(src, mapping[src])
    return text


def _localized_markup(request_id, lang):
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
    labels = {
        "fa": ("🔎 مشاهده درخواست", "⏳ در حال بررسی", "✅ انجام شد", "❌ رد درخواست"),
        "en": ("🔎 View request", "⏳ Under review", "✅ Completed", "❌ Reject request"),
        "ar": ("🔎 عرض الطلب", "⏳ قيد المراجعة", "✅ تم الإنجاز", "❌ رفض الطلب"),
    }[lang]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(labels[0], callback_data=f"panel:req:{request_id}")],
        [InlineKeyboardButton(labels[1], callback_data=f"panel:review:{request_id}"),
         InlineKeyboardButton(labels[2], callback_data=f"panel:approve:{request_id}")],
        [InlineKeyboardButton(labels[3], callback_data=f"panel:reject:{request_id}")],
    ])


def install(app, B):
    if getattr(B, "_telegram_notification_guard", False):
        return

    async def notify_admins(application, message, request_id=None, inline=None, files=None):
        admins = list(getattr(B, "ADM", set()) or [])
        if not admins:
            log.warning("No Telegram admins configured; notification not sent")
            return False

        lang = _request_lang(B, request_id) if request_id else "fa"
        localized_message = _localize_text(message, lang)
        markup = inline if inline is not None else (_localized_markup(request_id, lang) if request_id else None)

        ok = True
        bot = application.bot
        for aid in admins:
            delivered = False
            for attempt in range(3):
                try:
                    await bot.send_message(chat_id=int(aid), text=str(localized_message), reply_markup=markup)
                    delivered = True
                    break
                except Exception:
                    if attempt == 2:
                        log.exception("admin text notification failed: admin=%s request=%s", aid, request_id)
                    else:
                        await asyncio.sleep(0.7 * (attempt + 1))

            for item in list(files or []):
                if not item:
                    continue
                kind = str(item.get("type", "photo")) if isinstance(item, dict) else "photo"
                file_id = item.get("file_id") if isinstance(item, dict) else str(item)
                if not file_id:
                    continue
                for attempt in range(3):
                    try:
                        if kind == "document":
                            await bot.send_document(chat_id=int(aid), document=file_id)
                        else:
                            await bot.send_photo(chat_id=int(aid), photo=file_id)
                        break
                    except Exception:
                        if attempt == 2:
                            log.exception("admin attachment notification failed: admin=%s request=%s", aid, request_id)
                        else:
                            await asyncio.sleep(0.7 * (attempt + 1))
            if not delivered:
                ok = False
        return ok

    B.notify_admins = notify_admins
    B._telegram_notification_guard = True
    log.info("Telegram notification guard installed with per-request language")