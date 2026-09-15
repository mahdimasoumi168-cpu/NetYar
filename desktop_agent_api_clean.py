"""Clean authenticated Desktop Agent API for NetYar.

Installed into the existing FastAPI server and Telegram Application.
CAPTCHA is never solved here; the service only relays the image and
human-entered codes for the matching request ID.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Any

from fastapi import File, Header, HTTPException, UploadFile
from pydantic import BaseModel
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import ApplicationHandlerStop, CallbackQueryHandler, MessageHandler, filters


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def digits(value: Any) -> str:
    return str(value or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


class Event(BaseModel):
    phase: str
    message: str = ""


class Result(BaseModel):
    success: bool
    attempt: int = 1
    phase: str = "result"
    message: str = ""


def install(app, B):
    if getattr(B, "_desktop_agent_clean_installed", False):
        return
    import server
    key = os.getenv("DESKTOP_AGENT_KEY", "").strip()
    if not key:
        return

    B.db.conn.executescript("""
        CREATE TABLE IF NOT EXISTS desktop_agent_jobs(
            request_id INTEGER PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'queued',
            phase TEXT NOT NULL DEFAULT 'idle',
            attempt INTEGER NOT NULL DEFAULT 1,
            captcha_code TEXT DEFAULT '',
            verify_code TEXT DEFAULT '',
            result TEXT DEFAULT '',
            message TEXT DEFAULT '',
            updated_at TEXT NOT NULL
        );
    """)
    B.db.conn.commit()

    def auth(header: str | None):
        if header != key:
            raise HTTPException(status_code=401, detail="invalid desktop agent key")

    def request_row(rid: int):
        return B.db.conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()

    def answer_map(rid: int) -> dict[str, str]:
        rows = B.db.conn.execute("SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id", (rid,)).fetchall()
        return {str(r["field_key"]): str(r["answer"] or r["file_id"] or "") for r in rows}

    def partner_telegram_id(rid: int) -> int | None:
        row = request_row(rid)
        if not row:
            return None
        a = answer_map(rid)
        try:
            pid = int(a.get("partner_id") or row["user_id"])
        except (TypeError, ValueError):
            return None
        link = B.db.conn.execute("SELECT telegram_user_id FROM partner_telegram_links WHERE partner_id=?", (pid,)).fetchone()
        if not link or not str(link["telegram_user_id"]).isdigit():
            return None
        return int(link["telegram_user_id"])

    def upsert_job(rid: int, status: str, phase: str, attempt: int | None = None, **extra):
        row = B.db.conn.execute("SELECT request_id FROM desktop_agent_jobs WHERE request_id=?", (rid,)).fetchone()
        if not row:
            B.db.conn.execute(
                "INSERT INTO desktop_agent_jobs(request_id,status,phase,attempt,captcha_code,verify_code,result,message,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (rid, status, phase, attempt or 1, extra.get("captcha_code", ""), extra.get("verify_code", ""), extra.get("result", ""), extra.get("message", ""), now()),
            )
        else:
            fields = ["status=?", "phase=?", "updated_at=?"]
            vals: list[Any] = [status, phase, now()]
            if attempt is not None:
                fields.append("attempt=?")
                vals.append(attempt)
            for name in ("captcha_code", "verify_code", "result", "message"):
                if name in extra:
                    fields.append(f"{name}=?")
                    vals.append(extra[name])
            vals.append(rid)
            B.db.conn.execute(f"UPDATE desktop_agent_jobs SET {', '.join(fields)} WHERE request_id=?", vals)
        B.db.conn.commit()

    @server.api.get("/desktop-agent/health")
    async def desktop_health(x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        return {"ok": True, "service": "NetYar Desktop Agent", "version": "2.0"}

    @server.api.get("/desktop-agent/next")
    async def desktop_next(x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        row = B.db.conn.execute("""
            SELECT r.id,r.tracking_code,r.service_key,r.status
            FROM requests r
            LEFT JOIN desktop_agent_jobs j ON j.request_id=r.id
            WHERE r.service_key='government'
              AND r.status IN ('reviewing','processing','awaiting_agent')
              AND (j.status IS NULL OR j.status IN ('queued','retry'))
            ORDER BY r.id ASC LIMIT 1
        """).fetchone()
        if not row:
            return {"ok": True, "job": None}
        rid = int(row["id"])
        upsert_job(rid, "queued", "idle")
        return {"ok": True, "job": {"request_id": rid, "tracking_code": row["tracking_code"], "answers": answer_map(rid)}}

    @server.api.get("/desktop-agent/job/{rid}")
    async def desktop_job(rid: int, x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        row = request_row(rid)
        if not row:
            raise HTTPException(status_code=404, detail="request not found")
        job = B.db.conn.execute("SELECT * FROM desktop_agent_jobs WHERE request_id=?", (rid,)).fetchone()
        return {"ok": True, "request": dict(row), "answers": answer_map(rid), "job": dict(job) if job else None}

    @server.api.post("/desktop-agent/job/{rid}/event")
    async def desktop_event(rid: int, body: Event, x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        if not request_row(rid):
            raise HTTPException(status_code=404, detail="request not found")
        upsert_job(rid, "running", body.phase, message=body.message[:500])
        return {"ok": True}

    @server.api.post("/desktop-agent/job/{rid}/captcha-image")
    async def desktop_captcha_image(rid: int, file: UploadFile = File(...), x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        row = request_row(rid)
        if not row:
            raise HTTPException(status_code=404, detail="request not found")
        data = await file.read()
        if not data or len(data) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="invalid image")
        target = partner_telegram_id(rid)
        if not target:
            raise HTTPException(status_code=404, detail="linked partner Telegram account not found")
        upsert_job(rid, "waiting_captcha", "captcha_sent")
        await app.bot.send_document(
            chat_id=target,
            document=InputFile(BytesIO(data), filename=file.filename or "captcha.png"),
            caption=f"🛡 تصویر کد امنیتی درخواست {row['tracking_code']}\n\nکد را از روی تصویر بخوانید و با دکمه زیر ارسال کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📩 ارسال کد کپچا", callback_data=f"dta:captcha:{rid}")]]),
        )
        return {"ok": True}

    async def request_code_callback(update, context):
        q = update.callback_query
        data = str(getattr(q, "data", ""))
        if not q or not data.startswith("dta:"):
            return
        parts = data.split(":")
        if len(parts) != 3 or parts[1] not in {"captcha", "verify"}:
            return
        rid = int(parts[2])
        if partner_telegram_id(rid) != q.from_user.id:
            await q.answer("این درخواست برای شما نیست.", show_alert=True)
            raise ApplicationHandlerStop
        B.S.setdefault(q.from_user.id, {})["desktop_agent_wait"] = parts[1]
        B.S[q.from_user.id]["desktop_agent_rid"] = rid
        await q.answer()
        await q.message.reply_text("🔢 کد را همینجا ارسال کنید:")
        raise ApplicationHandlerStop

    async def request_code_text(update, context):
        msg = update.message
        if not msg or not msg.text:
            return
        st = B.S.setdefault(update.effective_user.id, {})
        kind = st.get("desktop_agent_wait")
        rid = st.get("desktop_agent_rid")
        if kind not in {"captcha", "verify"} or not rid:
            return
        value = digits(msg.text).strip()
        if not value or len(value) > 32:
            await msg.reply_text("❌ کد نامعتبر است.")
            raise ApplicationHandlerStop
        field = "captcha_code" if kind == "captcha" else "verify_code"
        upsert_job(int(rid), "running", f"{kind}_code_received", **{field: value})
        st["desktop_agent_wait"] = None
        await msg.reply_text("✅ کد دریافت شد و به برنامه ویندوزی تحویل می‌شود.")
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(request_code_callback, pattern=r"^dta:(captcha|verify):"), group=-1000012)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, request_code_text), group=-1000012)

    @server.api.get("/desktop-agent/job/{rid}/codes")
    async def desktop_codes(rid: int, x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        row = B.db.conn.execute("SELECT captcha_code,verify_code,phase,attempt,status FROM desktop_agent_jobs WHERE request_id=?", (rid,)).fetchone()
        return {"ok": True, **(dict(row) if row else {"captcha_code":"","verify_code":"","phase":"idle","attempt":1,"status":"queued"})}

    @server.api.post("/desktop-agent/job/{rid}/request-verify")
    async def desktop_request_verify(rid: int, x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        row = request_row(rid)
        if not row:
            raise HTTPException(status_code=404, detail="request not found")
        target = partner_telegram_id(rid)
        if not target:
            raise HTTPException(status_code=404, detail="linked partner Telegram account not found")
        upsert_job(rid, "waiting_verify", "verify_requested")
        await app.bot.send_message(
            chat_id=target,
            text=f"🔐 کد تأیید درخواست {row['tracking_code']} را پس از دریافت از سامانه ارسال کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📩 ارسال کد تأیید", callback_data=f"dta:verify:{rid}")]]),
        )
        return {"ok": True}

    @server.api.post("/desktop-agent/job/{rid}/result")
    async def desktop_result(rid: int, body: Result, x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        row = request_row(rid)
        if not row:
            raise HTTPException(status_code=404, detail="request not found")
        state = "completed" if body.success else ("retry" if body.attempt < 3 else "failed")
        upsert_job(rid, state, body.phase, body.attempt, result=("success" if body.success else "failed"), message=body.message[:500])
        B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?", (state, now(), rid))
        B.db.conn.commit()
        target = partner_telegram_id(rid)
        if target:
            if body.success:
                text = f"✅ درخواست {row['tracking_code']} با موفقیت انجام شد.\nDashboard شناسایی شد."
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأیید", callback_data=f"dta:done:{rid}")]])
            elif body.attempt < 3:
                text = f"🔁 تلاش {body.attempt} ناموفق بود. برای تلاش بعدی آماده است."
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 تلاش مجدد", callback_data=f"dta:retry:{rid}")]])
            else:
                text = f"❌ درخواست {row['tracking_code']} پس از ۳ تلاش ناموفق بود."
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ رد", callback_data=f"dta:reject:{rid}")]])
            await app.bot.send_message(chat_id=target, text=text, reply_markup=kb)
        return {"ok": True, "status": state}

    async def decision(update, context):
        q = update.callback_query
        data = str(getattr(q, "data", ""))
        if not q or not data.startswith("dta:"):
            return
        parts = data.split(":")
        if len(parts) != 3 or parts[1] not in {"done", "retry", "reject"}:
            return
        rid = int(parts[2])
        if partner_telegram_id(rid) != q.from_user.id:
            await q.answer("این درخواست برای شما نیست.", show_alert=True)
            raise ApplicationHandlerStop
        if parts[1] == "retry":
            upsert_job(rid, "retry", "retry_requested")
            B.db.conn.execute("UPDATE requests SET status='awaiting_agent',updated_at=? WHERE id=?", (now(), rid))
            B.db.conn.commit(); text="🔁 درخواست برای تلاش مجدد ثبت شد."
        elif parts[1] == "done":
            B.db.conn.execute("UPDATE requests SET status='completed',updated_at=? WHERE id=?", (now(), rid)); B.db.conn.commit(); text="✅ درخواست تأیید شد."
        else:
            B.db.conn.execute("UPDATE requests SET status='rejected',updated_at=? WHERE id=?", (now(), rid)); B.db.conn.commit(); text="❌ درخواست رد شد."
        await q.answer(); await q.message.reply_text(text); raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(decision, pattern=r"^dta:(done|retry|reject):"), group=-1000013)
    B._desktop_agent_clean_installed = True
