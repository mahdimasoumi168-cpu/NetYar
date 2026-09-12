"""Bridge legacy admin callback names to the canonical rq:* request controller.

Several older service modules still emit panel:* callbacks. Keeping a small
compatibility bridge makes those buttons functional without duplicating the
request-control implementation.
"""
from telegram.ext import CallbackQueryHandler, ApplicationHandlerStop

MAP = {
    "req": "detail",
    "review": "review",
    "approve": "approve",
    "reject": "reject",
    "askcode": "ask",
    "payconfirm": "payconfirm",
}


def install(app, B):
    if getattr(B, "_legacy_callback_bridge", False):
        return

    async def bridge(update, context):
        q = update.callback_query
        if not q:
            return
        data = str(q.data or "")
        if not data.startswith("panel:"):
            return
        parts = data.split(":")
        if len(parts) != 3 or parts[1] not in MAP:
            return
        if not B.admin(q.from_user.id):
            await q.answer("دسترسی ندارید", show_alert=True)
            raise ApplicationHandlerStop
        try:
            int(parts[2])
        except Exception:
            await q.answer("شناسه درخواست نامعتبر است", show_alert=True)
            raise ApplicationHandlerStop
        q.data = f"rq:{MAP[parts[1]]}:{parts[2]}"
        # The canonical request controller is installed in the same
        # application. Call it directly so the legacy callback is handled
        # immediately and cannot fall through to an unrelated router.
        import telegram_request_control_v2 as RC
        await RC.cb(update, context, B)
        raise ApplicationHandlerStop

    app.add_handler(CallbackQueryHandler(bridge, pattern=r"^panel:(req|review|approve|reject|askcode|payconfirm):"), group=-122)
    B._legacy_callback_bridge = True
