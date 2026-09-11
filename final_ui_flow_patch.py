"""Final Telegram UI and government-data flow fixes.

- Render Telegram action menus as inline buttons attached to the bot message.
- Keep legacy text handlers by translating inline callbacks back to text updates.
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


def _inline_kb(bot, uid, rows):
    buttons = []
    for row in rows or []:
        out = []
        for item in row or []:
            label = _text(item)
            out.append(bot.InlineKeyboardButton(label, callback_data=_remember(uid, label)))
        if out:
            buttons.append(out)
    return bot.InlineKeyboardMarkup(buttons)


def _fake_update(update, label):
    """Build the small update surface used by the existing text router."""
    msg = copy.copy(update.callback_query.message)
    msg.text = label
    user = update.effective_user
    chat = update.effective_chat
    return SimpleNamespace(
        message=msg,
        effective_user=user,
        effective_chat=chat,
        callback_query=None,
    )


async def _ui_callback(update, context):
    q = update.callback_query
    await q.answer()
    entry = _UI.get(str(q.data or ""))
    if not entry:
        return await q.message.reply_text("❌ این گزینه منقضی شده است. لطفاً منو را دوباره باز کنید.")
    uid, label = entry
    if int(q.from_user.id) != uid:
        return await q.message.reply_text("❌ این دکمه برای کاربر دیگری است.")
    import bot as B
    fake = _fake_update(update, label)
    try:
        result = await B.router(fake, context)
        if result is None:
            # A few legacy paths use ptext/service_text directly rather than router.
            if await B.ptext(fake, context):
                return
            await B.service_text(fake, context)
    except Exception:
        log.exception("inline Telegram callback failed: %s", label)
        await q.message.reply_text("❌ در اجرای این گزینه خطایی رخ داد. دوباره تلاش کنید.")


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
        B.db.conn.execute(
            "UPDATE requests SET status='submitted',payment_status='paid',payment_method='partner_balance' WHERE id=?",
            (rid,),
        )
        B.db.conn.execute(
            "UPDATE partners SET balance=balance-?,updated_at=? WHERE id=?",
            (amount, B.now(), pid),
        )
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
            await context.bot.send_photo(chat_id=int(aid), photo=card_file, caption=f"🪪 کارت آمایش | {code}")
            if sim_file:
                await context.bot.send_document(chat_id=int(aid), document=sim_file, caption=f"📎 سند سیم‌کارت | {code}")
        except Exception:
            log.exception("Amayesh admin notification failed")
    reply_markup = B.partner_kb(st.get("lang", "fa")) if pid else B.main(uid)
    return await update.message.reply_text(
        f"✅ درخواست کارت آمایش ثبت شد.\n🎫 کد پیگیری: {code}",
        reply_markup=reply_markup,
    )


def install():
    import bot as B
    import telegram_runtime as TG
    from telegram import CallbackQueryHandler

    if getattr(B, "_final_ui_flow_installed", False):
        return

    # Replace every legacy reply keyboard with an inline keyboard attached to
    # the message. The existing text-based business logic remains unchanged.
    def inline_kb(rows):
        uid = getattr(B, "_ui_current_uid", None)
        if uid is None:
            # Most calls happen after a user is known; keep a deterministic
            # fallback for admin/system-generated messages.
            uid = 0
        return _inline_kb(B, uid, rows)

    B.kb = inline_kb

    old_build = TG.build
    def build_with_inline():
        app = old_build()
        app.add_handler(CallbackQueryHandler(_ui_callback, pattern=r"^ui:"))
        return app
    TG.build = build_with_inline

    # Make sure the current user's id is available before a menu is built.
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

    old_service_text = B.service_text
    async def service_text(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        t = _digits((update.message.text or "").strip())
        # Exact government identifier formats.
        if st.get("mode") == "gov_unique":
            if not re.fullmatch(r"9\d{9}", t):
                return await update.message.reply_text(
                    "❌ کد یکتا باید دقیقاً ۱۰ رقم باشد و با ۹ شروع شود.\nمثال: 9xxxxxxxxx",
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )
            st["gov_unique"] = t
            st["mode"] = "gov_special"
            return await update.message.reply_text(
                "🔖 کد اختصاصی مشترک را وارد کنید.\nباید دقیقاً ۱۲ رقم باشد و با ۱ شروع شود.",
                reply_markup=B.cancel_kb(st.get("lang", "fa")),
            )
        if st.get("mode") == "gov_special":
            if not re.fullmatch(r"1\d{11}", t):
                return await update.message.reply_text(
                    "❌ کد اختصاصی باید دقیقاً ۱۲ رقم باشد و با ۱ شروع شود.\nمثال: 1xxxxxxxxxxx",
                    reply_markup=B.cancel_kb(st.get("lang", "fa")),
                )
            st["gov_special"] = t
            if st.get("gov_doc_type") == "passport":
                st["mode"] = "gov_passport"
                return await update.message.reply_text("🛂 شماره گذرنامه/پاسپورت مشترک را وارد کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            st["mode"] = "gov_household"
            return await update.message.reply_text("👨‍👩‍👧‍👦 کد خانوار کارت آمایش را وارد کنید:", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        if st.get("mode") == "gov_household":
            if not re.fullmatch(r"\d{1,20}", t):
                return await update.message.reply_text("❌ کد خانوار را فقط به صورت عدد وارد کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            st["gov_household"] = t
            st["mode"] = "gov_photo"
            return await update.message.reply_text("📸 عکس کارت آمایش را ارسال کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        if st.get("mode") == "gov_photo" and st.get("gov_doc_type") == "amaysh":
            # This path is normally reached by media(), not text. Kept for safety.
            return await update.message.reply_text("📸 عکس کارت آمایش را ارسال کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
        if st.get("mode") == "gov_sim_doc_optional":
            if t in {"⏭ سند سیم‌کارت ندارم", "سند سیم‌کارت ندارم", "ندارم"}:
                return await _finalize_amayesh(update, context, st, st.get("gov_card_file", ""), "")
        return await old_service_text(update, context)
    B.service_text = service_text

    old_media = B.media
    async def media(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        fid = update.message.photo[-1].file_id if update.message.photo else (update.message.document.file_id if update.message.document else "")
        if st.get("mode") == "gov_photo" and st.get("gov_doc_type") == "amaysh":
            if not fid:
                return await update.message.reply_text("❌ عکس کارت آمایش را به صورت تصویر یا فایل ارسال کنید.", reply_markup=B.cancel_kb(st.get("lang", "fa")))
            st["gov_card_file"] = fid
            st["mode"] = "gov_sim_doc_optional"
            return await update.message.reply_text(
                "📎 اگر سند سیم‌کارت به نام مشترک را دارید، ارسال کنید.\nاگر ندارید، گزینه «⏭ سند سیم‌کارت ندارم» را بزنید.\nاین مورد اختیاری است.",
                reply_markup=B.kb([["📎 ارسال سند سیم‌کارت"], ["⏭ سند سیم‌کارت ندارم"], [B.CANCEL]]),
            )
        if st.get("mode") == "gov_sim_doc_optional":
            if not fid:
                return await update.message.reply_text("📎 لطفاً سند سیم‌کارت را به صورت تصویر یا فایل ارسال کنید؛ یا گزینه «⏭ سند سیم‌کارت ندارم» را بزنید.", reply_markup=B.kb([["⏭ سند سیم‌کارت ندارم"], [B.CANCEL]]))
            return await _finalize_amayesh(update, context, st, st.get("gov_card_file", ""), fid)
        return await old_media(update, context)
    B.media = media

    # The optional-upload button is just a prompt; the next media message is
    # handled by the media wrapper above.
    old_router = B.router
    async def router(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        t = (update.message.text or "").strip()
        if st.get("mode") == "gov_sim_doc_optional" and t in {"📎 ارسال سند سیم‌کارت"}:
            return await update.message.reply_text("📎 حالا تصویر یا فایل سند سیم‌کارت را ارسال کنید.", reply_markup=B.kb([["⏭ سند سیم‌کارت ندارم"], [B.CANCEL]]))
        return await old_router(update, context)
    B.router = router

    B._final_ui_flow_installed = True
    log.info("final UI flow patch installed")
