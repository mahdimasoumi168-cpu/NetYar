"""Final Telegram partner-service dispatch safety layer.

This layer is intentionally small: it installs missing/stale service entry
points after all legacy feature modules have loaded, so inline partner buttons
never fall through to the generic 'service unavailable' recovery path.
"""
from telegram.ext import ApplicationHandlerStop


def install(app, B):
    if getattr(B, "_service_dispatch_final", False):
        return

    async def topup(update, context):
        uid = update.effective_user.id
        st = B.S.setdefault(uid, {})
        pid = st.get("partner_id")
        if not pid:
            return await update.effective_message.reply_text(
                "❌ ابتدا وارد پنل همکاران شوید.",
                reply_markup=B.main(uid),
            )
        row = B.db.conn.execute(
            "SELECT id,name,phone,balance FROM partners WHERE id=? AND active=1 LIMIT 1",
            (int(pid),),
        ).fetchone()
        if not row:
            st.pop("partner_id", None)
            st["partner_active"] = False
            st["mode"] = None
            return await update.effective_message.reply_text(
                "❌ حساب همکار فعال نیست. لطفاً دوباره وارد شوید.",
                reply_markup=B.main(uid),
            )
        st["mode"] = "topup_amount"
        return await update.effective_message.reply_text(
            "💰 شارژ حساب\n\nمبلغ شارژ را به تومان وارد کنید:",
            reply_markup=B.cancel_kb(st.get("lang", "fa")),
        )

    # The canonical UI dispatcher resolves B.topup at callback time. If a
    # later legacy module replaced it or never supplied it, this stable entry
    # point keeps the button executable.
    B.topup = topup

    # Common legacy aliases used by older button labels.
    aliases = {
        "pgov": "gov",
        "government": "gov",
        "printing": "prt",
        "print": "prt",
        "sim": "sim_start",
        "tracking": "ptrack",
        "history": "phistory",
    }
    for alias, target in aliases.items():
        if not callable(getattr(B, alias, None)) and callable(getattr(B, target, None)):
            setattr(B, alias, getattr(B, target))

    B._service_dispatch_final = True
