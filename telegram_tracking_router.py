"""Route the public tracking menu into the tracking lookup state."""
def install(B):
    if getattr(B,"_tracking_router_installed",False): return
    old=B.router
    async def router(update,context):
        t=(getattr(getattr(update,"message",None),"text","") or "").strip()
        if t in {"🎫 پیگیری","پیگیری","Tracking"}:
            uid=update.effective_user.id; B.S.setdefault(uid,{})["mode"]="public_tracking"
            return await update.message.reply_text("🎫 کد پیگیری را وارد کنید:",reply_markup=B.cancel_kb(B.S[uid].get("lang","fa")))
        return await old(update,context)
    B.router=router; B._tracking_router_installed=True
