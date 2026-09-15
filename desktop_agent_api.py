"""Secure Desktop Agent API for the NetYar Windows helper.

The desktop agent never solves CAPTCHA. It only relays the CAPTCHA image to the
linked partner, waits for a human-entered code, and continues the workflow.
The API is intentionally small and authenticated by DESKTOP_AGENT_KEY.
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


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _digits(s: Any) -> str:
    return str(s or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


class ResultPayload(BaseModel):
    success: bool
    attempt: int = 1
    phase: str = "result"
    message: str = ""


class EventPayload(BaseModel):
    phase: str
    message: str = ""



def install(app, B):
    if getattr(B, "_desktop_agent_api", False):
        return

    expected = os.getenv("DESKTOP_AGENT_KEY", "").strip()
    if not expected:
        # Do not expose an unauthenticated automation surface in production.
        B.api.get("/desktop-agent/health")(lambda: {"ok": False, "error": "DESKTOP_AGENT_KEY is not configured"})
        B._desktop_agent_api = True
        return

    B.db.conn.executescript(
        """
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
        """
    )
    B.db.conn.commit()

    def auth(key: str | None):
        if key != expected:
            raise HTTPException(status_code=401, detail="invalid desktop agent key")

    def req_row(rid: int):
        return B.db.conn.execute(
            "SELECT id,tracking_code,user_id,service_key,status,amount,payment_status,payment_method,created_at,updated_at FROM requests WHERE id=?",
            (rid,),
        ).fetchone()

    def answers(rid: int) -> dict[str, str]:
        rows = B.db.conn.execute(
            "SELECT field_key,answer,file_id FROM request_answers WHERE request_id=? ORDER BY id",
            (rid,),
        ).fetchall()
        out: dict[str, str] = {}
        for r in rows:
            out[str(r["field_key"])] = str(r["answer"] or r["file_id"] or "")
        return out

    def partner_uid(rid: int) -> int | None:
        r = req_row(rid)
        if not r:
            return None
        a = answers(rid)
        pid = a.get("partner_id") or str(r["user_id"])
        try:
            x = B.db.conn.execute(
                "SELECT telegram_user_id FROM partner_telegram_links WHERE partner_id=?",
                (int(pid),),
            ).fetchone()
            return int(x["telegram_user_id"]) if x and str(x["telegram_user_id"]).isdigit() else None
        except Exception:
            return None

    async def send_to_partner(rid: int, image: bytes, filename: str, caption: str, callback_prefix: str):
        if not getattr(B, "telegram_app", None):
            raise HTTPException(status_code=503, detail="telegram is not ready")
        target = partner_uid(rid)
        if not target:
            raise HTTPException(status_code=404, detail="linked partner Telegram account not found")
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("📩 ارسال کد", callback_data=f"dta:{callback_prefix}:{rid}")]]
        )
        await B.telegram_app.bot.send_document(
            chat_id=target,
            document=InputFile(BytesIO(image), filename=filename),
            caption=caption,
            reply_markup=markup,
        )
        return target

    @B.api.get("/desktop-agent/health")
    async def agent_health(x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        return {"ok": True, "service": "NetYar Desktop Agent", "version": "1.0"}

    @B.api.get("/desktop-agent/next")
    async def next_job(x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        row = B.db.conn.execute(
            """
            SELECT r.id,r.tracking_code,r.service_key,r.status,j.status AS agent_status,j.phase,j.attempt
            FROM requests r
            LEFT JOIN desktop_agent_jobs j ON j.request_id=r.id
            WHERE r.service_key='government'
              AND r.status IN ('reviewing','processing','awaiting_agent')
              AND (j.status IS NULL OR j.status IN ('queued','running','retry'))
            ORDER BY r.id ASC LIMIT 1
            """
        ).fetchone()
        if not row:
            return {"ok": True, "job": None}
        rid = int(row["id"])
        B.db.conn.execute(
            "INSERT OR IGNORE INTO desktop_agent_jobs(request_id,status,phase,attempt,updated_at) VALUES(?,?,?,?,?)",
            (rid, "queued", "idle", 1, _now()),
        )
        B.db.conn.commit()
        return {"ok": True, "job": {"request_id": rid, "tracking_code": row["tracking_code"], "answers": answers(rid)}}

    @B.api.get("/desktop-agent/job/{rid}")
    async def get_job(rid: int, x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        r = req_row(rid)
        if not r:
            raise HTTPException(status_code=404, detail="request not found")
        j = B.db.conn.execute("SELECT * FROM desktop_agent_jobs WHERE request_id=?", (rid,)).fetchone()
        return {
            "ok": True,
            "request": dict(r),
            "answers": answers(rid),
            "job": dict(j) if j else None,
        }

    @B.api.post("/desktop-agent/job/{rid}/event")
    async def event(rid: int, body: EventPayload, x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        if not req_row(rid):
            raise HTTPException(status_code=404, detail="request not found")
        B.db.conn.execute(
            "INSERT INTO desktop_agent_jobs(request_id,status,phase,attempt,message,updated_at) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(request_id) DO UPDATE SET status='running',phase=excluded.phase,message=excluded.message,updated_at=excluded.updated_at",
            (rid, "running", body.phase, 1, body.message[:500], _now()),
        )
        B.db.conn.commit()
        return {"ok": True}

    @B.api.post("/desktop-agent/job/{rid}/captcha-image")
    async def captcha_image(
        rid: int,
        file: UploadFile = File(...),
        x_desktop_agent_key: str | None = Header(default=None),
    ):
        auth(x_desktop_agent_key)
        if not req_row(rid):
            raise HTTPException(status_code=404, detail="request not found")
        data = await file.read()
        if not data or len(data) > 8 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="invalid image")
        B.db.conn.execute(
            "INSERT INTO desktop_agent_jobs(request_id,status,phase,attempt,updated_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(request_id) DO UPDATE SET status='waiting_captcha',phase='captcha_sent',updated_at=excluded.updated_at",
            (rid, "waiting_captcha", "captcha_sent", 1, _now()),
        )
        B.db.conn.commit()
        target = await send_to_partner(
            rid,
            data,
            file.filename or "captcha.png",
            f"🛡 کپچا درخواست {req_row(rid)['tracking_code']}\n\nکپچا را به‌صورت انسانی مشاهده کنید و کد را با دکمه «📩 ارسال کد» وارد کنید.",
            "captcha",
        )
        return {"ok": True, "partner_telegram_id": target}

    async def code_button(u, c):
        q = u.callback_query
        if not q or not str(q.data or "").startswith("dta:"):
            return
        p = q.data.split(":")
        if len(p) != 3:
            return
        rid = int(p[2])
        r = req_row(rid)
        if not r:
            await q.answer("درخواست پیدا نشد", show_alert=True)
            return
        target = partner_uid(rid)
        if target != q.from_user.id:
            await q.answer("این درخواست برای شما نیست", show_alert=True)
            return
        kind = p[1]
        B.S.setdefault(q.from_user.id, {})["desktop_agent_wait"] = kind
        B.S[q.from_user.id]["desktop_agent_rid"] = rid
        await q.answer()
        await q.message.reply_text("🔢 کد را همینجا ارسال کنید:")
        raise ApplicationHandlerStop

    async def code_text(u, c):
        m = u.message
        st = B.S.setdefault(u.effective_user.id, {})
        kind = st.get("desktop_agent_wait")
        rid = st.get("desktop_agent_rid")
        if kind not in {"captcha", "verify"} or not rid or not (m and m.text):
            return
        value = _digits(m.text.strip())
        if not value or len(value) > 32:
            await m.reply_text("❌ کد نامعتبر است.")
            raise ApplicationHandlerStop
        col = "captcha_code" if kind == "captcha" else "verify_code"
        B.db.conn.execute(
            f"INSERT INTO desktop_agent_jobs(request_id,status,phase,attempt,{col},updated_at) VALUES(?,?,?,?,?,?) "
            f"ON CONFLICT(request_id) DO UPDATE SET status='running',phase=?,{col}=excluded.{col},updated_at=excluded.updated_at",
            (int(rid), "running", f"{kind}_code_received", 1, value, _now(), f"{kind}_code_received"),
        )
        B.db.conn.commit()
        st["desktop_agent_wait"] = None
        await m.reply_text("✅ کد دریافت شد و برای برنامه ویندوزی ارسال می‌شود.")
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(code_button, pattern=r"^dta:(captcha|verify):"), group=-1000011)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, code_text), group=-1000011)

    @B.api.get("/desktop-agent/job/{rid}/codes")
    async def codes(rid: int, x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        j = B.db.conn.execute("SELECT captcha_code,verify_code,phase,attempt,status FROM desktop_agent_jobs WHERE request_id=?", (rid,)).fetchone()
        if not j:
            return {"ok": True, "captcha_code": "", "verify_code": "", "phase": "idle", "attempt": 1, "status": "queued"}
        return {"ok": True, **dict(j)}

    @B.api.post("/desktop-agent/job/{rid}/request-verify")
    async def request_verify(rid: int, x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        if not req_row(rid):
            raise HTTPException(status_code=404, detail="request not found")
        target = partner_uid(rid)
        if not target:
            raise HTTPException(status_code=404, detail="linked partner Telegram account not found")
        B.db.conn.execute(
            "INSERT INTO desktop_agent_jobs(request_id,status,phase,attempt,updated_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(request_id) DO UPDATE SET status='waiting_verify',phase='verify_requested',updated_at=excluded.updated_at",
            (rid, "waiting_verify", "verify_requested", 1, _now()),
        )
        B.db.conn.commit()
        await B.telegram_app.bot.send_message(
            chat_id=target,
            text=f"🔐 کد تأیید درخواست {req_row(rid)['tracking_code']} آماده دریافت است.\n\nپس از دریافت پیام سامانه، دکمه زیر را بزنید و کد را ارسال کنید.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📩 ارسال کد", callback_data=f"dta:verify:{rid}")]]),
        )
        return {"ok": True}

    @B.api.post("/desktop-agent/job/{rid}/result")
    async def result(rid: int, body: ResultPayload, x_desktop_agent_key: str | None = Header(default=None)):
        auth(x_desktop_agent_key)
        if not req_row(rid):
            raise HTTPException(status_code=404, detail="request not found")
        status = "success" if body.success else ("retry" if body.attempt < 3 else "failed")
        B.db.conn.execute(
            "INSERT INTO desktop_agent_jobs(request_id,status,phase,attempt,result,message,updated_at) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(request_id) DO UPDATE SET status=excluded.status,phase=excluded.phase,attempt=excluded.attempt,result=excluded.result,message=excluded.message,updated_at=excluded.updated_at",
            (rid, status, body.phase, body.attempt, "success" if body.success else "failed", body.message[:500], _now()),
        )
        B.db.conn.execute("UPDATE requests SET status=?,updated_at=? WHERE id=?", ("completed" if body.success else status, _now(), rid))
        B.db.conn.commit()
        target = partner_uid(rid)
        if target and getattr(B, "telegram_app", None):
            if body.success:
                text = f"✅ درخواست {req_row(rid)['tracking_code']} با موفقیت وارد شد.\nکلمه Dashboard شناسایی شد."
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ تأیید", callback_data=f"dta:done:{rid}")]])
            elif body.attempt < 3:
                text = f"🔁 تلاش {body.attempt} ناموفق بود.\nبرنامه برای تلاش بعدی آماده می‌شود."
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔁 تلاش مجدد", callback_data=f"dta:retry:{rid}")]])
            else:
                text = f"❌ درخواست {req_row(rid)['tracking_code']} پس از ۳ تلاش ناموفق بود."
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("❌ رد", callback_data=f"dta:reject:{rid}")]])
            await B.telegram_app.bot.send_message(chat_id=target, text=text, reply_markup=kb)
        return {"ok": True, "status": status}

    async def decision(u, c):
        q = u.callback_query
        if not q or not str(q.data or "").startswith("dta:"):
            return
        p = q.data.split(":")
        if len(p) != 3 or p[1] not in {"done", "retry", "reject"}:
            return
        rid = int(p[2])
        if partner_uid(rid) != q.from_user.id:
            await q.answer("این درخواست برای شما نیست", show_alert=True)
            return
        new_status = {"done": "confirmed", "retry": "retry", "reject": "rejected"}[p[1]]
        B.db.conn.execute("UPDATE desktop_agent_jobs SET status=?,phase=?,updated_at=? WHERE request_id=?", (new_status, p[1], _now(), rid))
        B.db.conn.commit()
        await q.answer("ثبت شد")
        await q.message.reply_text("✅ وضعیت درخواست ثبت شد.")
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(decision, pattern=r"^dta:(done|retry|reject):"), group=-1000010)
    B._desktop_agent_api = True
