"""Rubika reliability fallback and production UI hardening."""
import asyncio
import hashlib
import json
import logging
import os
import re
import time
from collections import OrderedDict

log = logging.getLogger("netyar.rubika_polling_fallback")
_RB_SEEN = OrderedDict(); _RB_SEEN_TTL = 120
_RB_FAST_SEEN = OrderedDict(); _RB_FAST_TTL = 2.0
_RB_NOTIFIED_REQUESTS = OrderedDict(); _RB_NOTIFY_TTL = 86400

def normalize_phone(value):
    s=str(value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"));s=re.sub(r"[\s\-()]+","",s)
    if s.startswith("+98"):s="0"+s[3:]
    elif s.startswith("0098"):s="0"+s[4:]
    return s

def _inline_keypad(rows):
    return {"rows":[{"buttons":[{"id":str(i[0]),"type":"Simple","button_text":str(i[1])} for i in (row or []) if isinstance(i,(tuple,list)) and len(i)>=2]} for row in (rows or []) if row]}

def _patch_rubika_inline_ui(rb):
    if getattr(rb,"_netyar_inline_ui_installed",False):return
    def inline_send(chat,text,rows=None):
        payload={"chat_id":str(chat),"text":str(text or ""),"chat_keypad_type":"Remove"}
        if rows:payload["inline_keypad"]=_inline_keypad(rows)
        return rb.call("sendMessage",payload)
    rb.send=inline_send;rb._netyar_inline_ui_installed=True

def _update_key(update):
    if not isinstance(update,dict):return ""
    u=update.get("update") if isinstance(update.get("update"),dict) else update;m=u.get("message") or u.get("new_message") or u.get("inline_message") or {}
    if not isinstance(m,dict):m={}
    for k in ("message_id","update_id","id"):
        v=m.get(k) or u.get(k)
        if v:return f"id:{v}"
    try:raw=json.dumps(update,ensure_ascii=False,sort_keys=True,separators=(",",":"))
    except Exception:raw=repr(update)
    return "hash:"+hashlib.sha256(raw.encode()).hexdigest()

def _semantic_key(update,server):
    try:
        u=server._rubika_inner(update) if hasattr(server,"_rubika_inner") else update;m=server._rubika_message(u) if hasattr(server,"_rubika_message") else {}
        uid=server._rubika_user(update);txt=str(m.get("text") or m.get("aux_data") or "");return f"{uid}|{txt}"
    except Exception:return ""

def _seen_update(update,server):
    key=_update_key(update);now=time.monotonic()
    for k,t in list(_RB_SEEN.items()):
        if now-t>_RB_SEEN_TTL:_RB_SEEN.pop(k,None)
    if key and key in _RB_SEEN:return True
    if key:_RB_SEEN[key]=now
    while len(_RB_SEEN)>4096:_RB_SEEN.popitem(last=False)
    sk=_semantic_key(update,server)
    for k,t in list(_RB_FAST_SEEN.items()):
        if now-t>_RB_FAST_TTL:_RB_FAST_SEEN.pop(k,None)
    if sk and sk in _RB_FAST_SEEN:return True
    if sk:_RB_FAST_SEEN[sk]=now
    while len(_RB_FAST_SEEN)>2048:_RB_FAST_SEEN.popitem(last=False)
    return False

def _notified_request(rid):
    now=time.monotonic()
    for k,t in list(_RB_NOTIFIED_REQUESTS.items()):
        if now-t>_RB_NOTIFY_TTL:_RB_NOTIFIED_REQUESTS.pop(k,None)
    if rid in _RB_NOTIFIED_REQUESTS:return True
    _RB_NOTIFIED_REQUESTS[rid]=now
    while len(_RB_NOTIFIED_REQUESTS)>2048:_RB_NOTIFIED_REQUESTS.popitem(last=False)
    return False

def _rubika_request_snapshot(rb,uid):
    try:
        row=rb.db.conn.execute("SELECT r.id FROM users u LEFT JOIN requests r ON r.user_id=u.id WHERE u.platform='rubika' AND u.external_id=? ORDER BY r.id DESC LIMIT 1",(str(uid),)).fetchone()
        return int(row["id"]) if row and row["id"] is not None else 0
    except Exception:return 0

async def _notify_telegram_admins(server,rb,uid,before_request_id):
    try:
        app=getattr(server,"telegram_app",None)
        if app is None:return
        import bot as telegram_bot
        admin_ids=list(getattr(telegram_bot,"ADM",[]) or [])
        if not admin_ids:return
        row=rb.db.conn.execute("SELECT r.id,r.tracking_code,r.service_key,r.status,r.amount FROM requests r JOIN users u ON u.id=r.user_id WHERE u.platform='rubika' AND u.external_id=? AND r.id>? ORDER BY r.id DESC LIMIT 1",(str(uid),int(before_request_id or 0))).fetchone()
        if not row:return
        rid=int(row["id"])
        if _notified_request(rid):return
        text=f"👔 مدیر — درخواست جدید از روبیکا\n\n🆕 درخواست خدمات ثبت شد\n🎫 کد پیگیری: {row['tracking_code'] or '-'}\n🛠 خدمت: {row['service_key'] or '-'}\n📊 وضعیت: {row['status'] or '-'}\n💰 مبلغ: {int(row['amount'] or 0):,} تومان\n👤 شناسه روبیکا: {uid}"
        markup=None
        try:
            from telegram_service_notifications import _admin_markup
            markup=_admin_markup(rid)
        except Exception:pass
        for aid in admin_ids:
            try:await app.bot.send_message(chat_id=int(aid),text=text,reply_markup=markup)
            except Exception:log.exception("Rubika admin notification failed: %s",aid)
    except Exception:log.exception("Rubika-to-Telegram admin notification failed")

async def _poll(server,rb):
    offset_id=None;log.warning("Rubika getUpdates fallback started")
    while True:
        try:
            payload={"limit":10}
            if offset_id:payload["offset_id"]=offset_id
            result=await asyncio.to_thread(rb.call,"getUpdates",payload)
            if not isinstance(result,dict):await asyncio.sleep(.2);continue
            updates=result.get("updates") or [];updates=updates if isinstance(updates,list) else []
            nxt=result.get("next_offset_id")
            if nxt:offset_id=str(nxt)
            for update in updates:
                if not isinstance(update,dict) or _seen_update(update,server):continue
                uid=None
                try:
                    uid=server._rubika_user(update);before=_rubika_request_snapshot(rb,uid)
                    await server._run_rubika(update,rb)
                    await _notify_telegram_admins(server,rb,uid,before)
                except Exception:log.exception("Rubika update processing failed: user=%s",uid)
                await asyncio.sleep(.05)
            if not updates:await asyncio.sleep(.15)
        except asyncio.CancelledError:return
        except Exception:log.exception("Rubika getUpdates fallback failed");await asyncio.sleep(1)

def install():
    import server
    if getattr(server,"_rubika_polling_fallback_installed",False):return
    original=server._initialize_integrations
    async def initialize():
        await original()
        force=os.getenv("RUBIKA_FORCE_POLLING","0").strip().lower() in {"1","true","yes","on"}
        if getattr(server,"rubika_ready",False) and not force:return
        try:
            import rubika_v2 as rb
            import partner_pricing
            rb.normalize_phone=normalize_phone;server._patch_rubika(rb);_patch_rubika_inline_ui(rb)
            partner_pricing.install_rubika(rb)
            try:
                import rubika_iranian_complaints
                rubika_iranian_complaints.install(rb)
                log.info("Rubika Iranian subscriber UX installed")
            except Exception:log.exception("Rubika Iranian subscriber UX could not be installed")
            try:
                import rubika_admin_control_v5
                rubika_admin_control_v5.install();log.info("Rubika full admin control installed")
            except Exception:log.exception("Rubika full admin control could not be installed")
            task=getattr(server,"_rubika_polling_task",None)
            if task is None or task.done():server._rubika_polling_task=asyncio.create_task(_poll(server,rb))
            server.rubika_ready=True;log.warning("Rubika is online with getUpdates polling fallback and inline UI")
        except Exception:server.rubika_ready=False;log.exception("Could not start Rubika getUpdates fallback")
    server._initialize_integrations=initialize;server._rubika_polling_fallback_installed=True;log.info("Rubika polling fallback installed")
