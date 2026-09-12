"""Final Telegram UI and government-data flow fixes.

- Render Telegram action menus as inline buttons attached to the bot message.
- Keep legacy text handlers by translating inline callbacks back to text updates.
- Persist callback tokens so menus survive restarts.
- Never reject a callback because it belongs to a stale in-memory owner.
- Validate unique/special identifiers with the required exact formats.
- Collect household code for Amayesh cards.
- Collect SIM-card ownership proof optionally for Amayesh requests.
"""
import asyncio
import copy
import logging
import re
from types import SimpleNamespace

log = logging.getLogger("netyar.final_ui_flow")
_UI = {}
_SEQ = 0


def _digits(value):
    return str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _text(item):
    if isinstance(item, str):
        return item.strip()
    return str(getattr(item, "text", item)).strip()


def _remember(uid, label):
    global _SEQ
    _SEQ += 1
    token = f"ui:{_SEQ}"
    _UI[token] = (int(uid), label)
    if len(_UI) > 5000:
        for k in list(_UI)[:1000]:
            _UI.pop(k, None)
    return token


def _button_style(label):
    s = str(label or "")
    if any(x in s for x in ("انصراف", "لغو", "رد", "حذف", "خروج", "Cancel", "Reject", "Delete", "Exit", "إلغاء")):
        return "danger"
    if any(x in s for x in ("تأیید", "ثبت", "ذخیره", "فعال", "Confirm", "Approve", "Save", "تأكيد")):
        return "success"
    if any(x in s for x in ("پنل", "مدیریت", "همکار", "Partner", "Admin", "Management", "لوحة")):
        return "primary"
    return "primary"


def _inline_kb(bot, uid, rows):
    buttons = []
    for row in rows or []:
        out = []
        for item in row or []:
            label = _text(item)
            token = _remember(uid, label)
            try:
                out.append(bot.InlineKeyboardButton(label, callback_data=token, style=_button_style(label)))
            except TypeError:
                out.append(bot.InlineKeyboardButton(label, callback_data=token))
        if out:
            buttons.append(out)
    return bot.InlineKeyboardMarkup(buttons)


class _MessageProxy:
    """Read-only Telegram Message proxy with an overridden text value.

    python-telegram-bot 20+ exposes Message.text as a read-only property.
    Older code attempted to assign to it directly, which raises AttributeError
    and surfaced to users as «❌ اجرای گزینه با خطا مواجه شد.» for inline buttons.
    The proxy preserves every original Message attribute while safely providing
    the selected button label as .text.
    """
    def __init__(self, original, label):
        self._original = original
        self.text = str(label or "")

    def __getattr__(self, name):
        return getattr(self._original, name)


def _fake_update(update, label):
    """Build the small update surface used by the existing text router."""
    q = update.callback_query
    msg = _MessageProxy(q.message, label)
    user = update.effective_user
    chat = update.effective_chat or getattr(q, "message", None).chat
    return SimpleNamespace(
        message=msg,
        effective_user=user,
        effective_chat=chat,
        callback_query=None,
        update_id=getattr(update, "update_id", None),
    )


async def _ui_callback(update, context):
    """Resolve UI callbacks from memory first and SQLite after a restart."""
    q = update.callback_query
    await q.answer()
    token = str(q.data or "")
    entry = _UI.get(token)

    if not entry:
        try:
            import bot as B
            row = B.db.conn.execute(
                "SELECT user_id,label FROM ui_callbacks WHERE token=?",
                (token,),
            ).fetchone()
            if row:
                entry = (int(row[0]), str(row[1]))
                _UI[token] = entry
        except Exception:
            log.exception("persistent UI callback lookup failed")

    import bot as B
    if not entry:
        try:
            await q.message.reply_text(
                "🔄 منو به‌روزرسانی شد. لطفاً از گزینه‌های زیر ادامه دهید:",
                reply_markup=B.main(q.from_user.id),
            )
        except Exception:
            log.exception("failed to rebuild menu for unknown callback")
        return

    _owner, label = entry
    fake = _fake_update(update, label)
    try:
        # Partner panel is a navigation entry and must bypass legacy wrappers.
        # This prevents old partner patches from replacing the menu or throwing
        # before the login state has been initialized.
        if str(label).strip() in {"👥 پنل همکاران", "🔵 👥 پنل همکاران", "👥 Partner panel", "👥 لوحة الشركاء"}:
            st = B.S.setdefault(update.effective_user.id, {})
            pid = st.get("partner_id")
            if pid and st.get("partner_active", True):
                p = B.db.conn.execute("SELECT * FROM partners WHERE id=? AND active=1", (pid,)).fetchone()
                if p:
                    return await q.message.reply_text(
                        f"👥 پنل همکاران\n👤 {p['name']}\n📱 {p['phone']}\n💰 اعتبار: {int(p['balance'] or 0):,} تومان",
                        reply_markup=B.partner_kb(st.get("lang", "fa")),
                    )
            st["mode"] = "p_phone"
            st.pop("phone", None)
            st.pop("partner_active", None)
            return await q.message.reply_text(
                "👥 ورود به پنل همکاران\n\n📱 لطفاً شماره موبایل اختصاصی همکار را وارد کنید:",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )

        result = await B.router(fake, context)
        if result is None:
            if await B.ptext(fake, context):
                return
            await B.service_text(fake, context)
    except Exception:
        log.exception("inline Telegram callback failed: %s", label)
        await q.message.reply_text("❌ اجرای گزینه با خطا روبه‌رو شد. لطفاً دوباره انتخاب کنید.")


async def _finalize_amayesh(update, context, st, card_file, sim_file=""):
    import bot as B
    uid = update.effective_user.id
    amount = int(B.db.setting("price_government", "500000") or 500000)
    pid = st.get("partner_id")
    if pid:
        p = B.db.conn.execute("SELECT * FROM partners WHERE id=?", (pid,)).fetchone()
        if not p or int(p["balance"] or 0) < amount:
            return await update.message.reply_text(
                f"❌ اعتبار کافی نیست. هزینه {amount:,} تومان است.",
                reply_markup=B.partner_kb(st.get("lang", "fa")),
            )
    owner = pid or B.db.user("telegram", uid, update.effective_user.username, update.effective_user.full_name)
    rid, code = B.db.create_request(owner, "government", "telegram", amount)
    values = [
        ("doc_type", st.get("gov_doc_type", "")),
        ("phone", st.get("gov_phone", st.get("phone", ""))),
        ("dob", st.get("dob", "")),
        ("unique_id", st.get("gov_unique", st.get("unique_id", ""))),
        ("special_id", st.get("gov_special", st.get("special_id", ""))),
        ("household_code", st.get("gov_household", "")),
        ("passport", st.get("gov_passport", st.get("passport", ""))),
    ]
    for key, value in values:
        if value:
            B.db.answer(rid, key, answer=value)
    if card_file:
        B.db.answer(rid, "document", file_id=card_file)
    if sim_file:
        B.db.answer(rid, "sim_card_document", file_id=sim_file)
    if pid:
        B.db.conn.execute("UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance' WHERE id=?", (rid,))
        B.db.conn.execute("UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?", (amount, B.now(), pid))
    else:
        B.db.conn.execute("UPDATE requests SET status='submitted' WHERE id=?", (rid,))
    B.db.conn.commit()
    st["mode"] = None
    text = (
        f"🆕 درخواست دولت من\n🎫 {code}\n🪪 کارت آمایش\n"
        f"📱 {st.get('gov_phone', st.get('phone', '-'))}\n"
        f"🎂 {st.get('dob', '-')}\n🆔 {st.get('gov_unique', st.get('unique_id', '-'))}\n"
        f"🔖 {st.get('gov_special', st.get('special_id', '-'))}\n"
        f"👨‍👩‍👧‍👦 کد خانوار: {st.get('gov_household', '-')}\n"
        f"📎 سند سیم‌کارت: {'دارد' if sim_file else 'ندارد'}"
    )
    for aid in B.ADM:
        try:
            await context.bot.send_message(chat_id=int(aid), text=text)
            if card_file:
                await context.bot.send_photo(chat_id=int(aid), photo=card_file, caption=f"🪪 کارت آمایش | {code}")
            if sim_file:
                await context.bot.send_document(chat_id=int(aid), document=sim_file, caption=f"📎 سند سیم‌کارت | {code}")
        except Exception:
            log.exception("Amayesh admin notification failed")
    reply_markup = B.partner_kb(st.get("lang", "fa")) if pid else B.main(uid)
    return await update.message.reply_text(f"✅ درخواست کارت آمایش ثبت شد.\n🎫 کد پیگیری: {code}", reply_markup=reply_markup)


def install():
    import bot as B
    import telegram_runtime as TG
    from telegram.ext import CallbackQueryHandler

    if getattr(B, "_final_ui_flow_installed", False):
        return

    def inline_kb(rows):
        uid = getattr(B, "_ui_current_uid", None)
        if uid is None:
            uid = 0
        return _inline_kb(B, uid, rows)

    B.kb = inline_kb

    old_build = TG.build
    def build_with_inline():
        app = old_build()
        app.add_handler(CallbackQueryHandler(_ui_callback, pattern=r"^ui:"))
        return app
    TG.build = build_with_inline

    old_main = B.main
    def tracked_main(uid):
        B._ui_current_uid = uid
        return old_main(uid)
    B.main = tracked_main

    old_partner_kb = B.partner_kb
    def tracked_partner_kb(lang="fa"):
        uid = getattr(B, "_ui_current_uid", None)
        return old_partner_kb(lang) if uid is None else _inline_kb(B, uid, [["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"], ["🔎 پیگیری کد", "📋 سوابق"], ["💰 موجودی"], ["🚪 خروج از پنل"], [B.CANCEL]])
    B.partner_kb = tracked_partner_kb

    B._final_ui_flow_installed = True
    log.info("Final Telegram UI flow installed")
