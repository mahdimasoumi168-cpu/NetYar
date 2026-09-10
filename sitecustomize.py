"""NetYar startup compatibility patch."""
from pathlib import Path

try:
    p = Path(__file__).with_name("bot.py")
    if p.exists():
        s = p.read_text(encoding="utf-8")
        original = s
        s = s.replace("async \n\ndef normalize_phone", "\ndef normalize_phone")
        s = s.replace("\ndef partner(u,c):", "\nasync def partner(u,c):")
        s = s.replace('if t in ("🎫 کد رهگیری تمدید کارت‌ها","📱 خدمات سیم کارت","📝 آزمون غربالگری و پیگیری"):','if t in ("🎫 کد رهگیری تمدید کارت‌ها","📱 خدمات سیم کارت"):')
        if s != original: p.write_text(s, encoding="utf-8")

    sp = Path(__file__).with_name("server.py")
    if sp.exists():
        s = sp.read_text(encoding="utf-8")
        old = '''    if telegram_app is None:\n        log.error("Telegram webhook called before Telegram application was ready")\n        return {"ok":False,"error":"telegram_not_ready"}'''
        new = '''    if telegram_app is None:\n        log.warning("Telegram webhook received during startup; acknowledging until application is ready")\n        return {"ok":True,"starting":True}'''
        if old in s: sp.write_text(s.replace(old,new), encoding="utf-8")
except Exception:
    pass

try:
    import json
    import rubika_v2 as _rb
    def _rb_message(update):
        if isinstance(update, dict) and isinstance(update.get("inline_message"), dict): return update["inline_message"]
        if isinstance(update, dict):
            m = update.get("message") or update.get("new_message") or update
            return m if isinstance(m, dict) else {}
        return {}
    def _rb_text(update):
        m = _rb_message(update)
        for key in ("text", "button_text"):
            if m.get(key): return str(m[key]).strip()
        aux = m.get("aux_data")
        if isinstance(aux, dict): return str(aux.get("button_id") or aux.get("button_text") or aux.get("text") or "").strip()
        if isinstance(aux, str):
            try:
                aux = json.loads(aux)
                if isinstance(aux, dict): return str(aux.get("button_id") or aux.get("button_text") or aux.get("text") or "").strip()
            except Exception: pass
        return ""
    def _rb_chat(update):
        m = _rb_message(update)
        return str(m.get("chat_id") or m.get("chat_key") or (update.get("chat_id") if isinstance(update, dict) else "") or "")
    def _rb_user(update):
        m = _rb_message(update); sender = m.get("sender") or {}
        return str(sender.get("user_id") or m.get("sender_id") or m.get("user_id") or (update.get("sender_id") if isinstance(update, dict) else "") or _rb_chat(update))
    def _rb_rows(rows):
        result=[]
        for row in rows or []:
            buttons=[]
            for i,item in enumerate(row or []):
                if isinstance(item,(tuple,list)) and len(item)>=2: bid,label=str(item[0]),str(item[1])
                else: bid,label=str(i),str(item)
                buttons.append({"id":bid,"type":"Simple","button_text":label})
            if buttons: result.append({"buttons":buttons})
        return result
    _rb.text_of=_rb_text; _rb.chat_of=_rb_chat; _rb.user_of=_rb_user; _rb.rows=_rb_rows; _rb._NETYAR_RUBIKA_PATCHED=True
except Exception:
    pass

try: import enhancements
except Exception: pass
try: import final_patch
except Exception: pass
try: import rubika_admin_patch
except Exception: pass
