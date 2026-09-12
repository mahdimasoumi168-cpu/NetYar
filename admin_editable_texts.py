"""Comprehensive Telegram text editor for administrators.

The editor discovers user-facing literal strings from the loaded NetYar Python
modules, gives the admin a paginated list, and stores exact replacements in the
existing admin_settings table. Outgoing Telegram messages are rewritten only
when their complete text exactly matches an edited source string, so business
logic and callback routing are not changed.
"""
from __future__ import annotations

import ast
import hashlib
import os
import sys
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters

_PREFIX = "ui_replace_"
_PAGE = "ui_text_page"
_STATE = "editable_text_hash"


def _kb(rows):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(str(t), callback_data=str(d)) for t, d in row] for row in rows]
    )


def _setting(B, key, default=""):
    try:
        return B.db.setting(key, default) or default
    except Exception:
        return default


def _save(B, key, value):
    B.db.set_setting(key, value)


def _is_ui_text(s: str) -> bool:
    if not isinstance(s, str):
        return False
    s = s.strip()
    if len(s) < 2 or len(s) > 700:
        return False
    if "\\n" in s:
        pass
    # Persian/Arabic, common UI emojis, or clearly user-facing Telegram text.
    if any("\\u0600" <= ch <= "\\u06ff" for ch in s):
        return True
    if any(ord(ch) >= 0x1F300 for ch in s):
        return True
    return False


def _modules_source_texts():
    found = {}
    for mod in list(sys.modules.values()):
        path = getattr(mod, "__file__", None)
        if not path or not path.endswith(".py"):
            continue
        if not os.path.isfile(path):
            continue
        # Only scan the application tree; do not inspect third-party packages.
        base = os.path.abspath(os.getcwd())
        full = os.path.abspath(path)
        if not (full == base or full.startswith(base + os.sep)):
            continue
        try:
            with open(full, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=full)
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    text = node.value.strip()
                    if _is_ui_text(text):
                        found[text] = True
        except Exception:
            continue
    return sorted(found)


def _catalog(B):
    items = _modules_source_texts()
    # Include important editable texts even when a runtime patch generated them.
    for key in ("welcome", "iranian", "contact", "complaint_prompt", "complaint_ok"):
        value = _setting(B, "ui_text_" + key, "")
        if value and value not in items:
            items.append(value)
    return sorted(set(items))


def _hid(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _original(B, hid):
    return _setting(B, "ui_original_" + hid, "")


def _override(B, original):
    return _setting(B, _PREFIX + _hid(original), "")


def _replace_text(text, B):
    if not isinstance(text, str) or not text:
        return text
    replacement = _override(B, text)
    return replacement or text


def _install_outgoing_editor(app, B):
    marker = "_netyar_text_editor_outgoing"
    if getattr(app, marker, False):
        return
    bot = app.bot
    old_send = bot.send_message
    old_edit = bot.edit_message_text

    async def send_message(*args, **kwargs):
        if "text" in kwargs:
            kwargs["text"] = _replace_text(kwargs["text"], B)
        elif len(args) >= 2:
            args = list(args)
            args[1] = _replace_text(args[1], B)
        return await old_send(*args, **kwargs)

    async def edit_message_text(*args, **kwargs):
        if "text" in kwargs:
            kwargs["text"] = _replace_text(kwargs["text"], B)
        elif len(args) >= 3:
            args = list(args)
            args[2] = _replace_text(args[2], B)
        return await old_edit(*args, **kwargs)

    bot.send_message = send_message
    bot.edit_message_text = edit_message_text
    setattr(app, marker, True)


def _page(B, page=0):
    items = _catalog(B)
    size = 8
    pages = max(1, (len(items) + size - 1) // size)
    page = max(0, min(page, pages - 1))
    rows = []
    for text in items[page * size:(page + 1) * size]:
        hid = _hid(text)
        _save(B, "ui_original_" + hid, text)
        label = text.replace("\n", " ")[:42]
        rows.append([(label, "adm:et:" + hid)])
    nav = []
    if page > 0:
        nav.append(("⬅️ قبلی", f"adm:etpage:{page-1}"))
    if page + 1 < pages:
        nav.append(("بعدی ➡️", f"adm:etpage:{page+1}"))
    if nav:
        rows.append(nav)
    rows.append([("🔎 تعداد متن‌های پیدا شده: " + str(len(items)), "adm:etnoop")])
    rows.append([("⬅️ پنل مدیریت", "adm:menu")])
    return rows, page, pages


def install(app, B):
    _install_outgoing_editor(app, B)

    async def cb(update, context):
        q = update.callback_query
        uid = q.from_user.id
        if not B.admin(uid):
            return
        await q.answer()
        st = B.S.setdefault(uid, {})
        data = q.data or ""

        if data in {"adm:ui_texts", "adm:ui_options"}:
            rows, page, pages = _page(B, 0)
            title = "🤖 ویرایش متن‌های ربات\n\nهمه متن‌های قابل تشخیص پروژه نمایش داده می‌شوند."
            return await q.message.reply_text(title, reply_markup=_kb(rows))

        if data.startswith("adm:etpage:"):
            try:
                page = int(data.rsplit(":", 1)[1])
            except Exception:
                page = 0
            rows, _, _ = _page(B, page)
            return await q.message.reply_text("✏️ ویرایش متن‌های ربات", reply_markup=_kb(rows))

        if data.startswith("adm:et:"):
            hid = data.split(":", 2)[2]
            original = _original(B, hid)
            if not original:
                return await q.message.reply_text("❌ متن پیدا نشد. دوباره فهرست متن‌ها را باز کنید.")
            st[_STATE] = hid
            st["editable_mode"] = "all_text"
            current = _override(B, original) or original
            return await q.message.reply_text(
                "✏️ ویرایش متن\n\n"
                "متن فعلی:\n" + current +
                "\n\nمتن جدید را همینجا ارسال کنید:\n"
                "برای نگه‌داشتن خط جدید، پیام را چندخطی ارسال کنید."
            )

        if data == "adm:etnoop":
            return

    async def text(update, context):
        uid = update.effective_user.id
        if not B.admin(uid):
            return
        st = B.S.setdefault(uid, {})
        if st.get("editable_mode") != "all_text":
            return
        value = (update.message.text or "")
        if not value.strip():
            return await update.message.reply_text("❌ متن خالی قابل ذخیره نیست.")
        hid = st.get(_STATE)
        original = _original(B, hid) if hid else ""
        if not original:
            st.pop("editable_mode", None)
            st.pop(_STATE, None)
            return await update.message.reply_text("❌ متن انتخاب‌شده منقضی شده است.")
        _save(B, _PREFIX + hid, value)
        st.pop("editable_mode", None)
        st.pop(_STATE, None)
        return await update.message.reply_text("✅ متن با موفقیت ذخیره شد و از این به بعد در پیام‌های دقیقاً مشابه اعمال می‌شود.")

    app.add_handler(
        CallbackQueryHandler(
            cb,
            pattern=r"^adm:(ui_texts|ui_options|etpage:|et:|etnoop$|menu$)",
        ),
        group=-30,
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text), group=-30)
    B._editable_texts_installed = True
