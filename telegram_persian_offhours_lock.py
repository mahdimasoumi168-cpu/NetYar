"""Persian-only UI. No working-hours lock: the bot is permanently 24/7."""
from telegram.ext import MessageHandler, CallbackQueryHandler, ApplicationHandlerStop, filters
def _open_now(B): return True
def install(app,B):
    if getattr(B,"_persian_24x7_lock_installed",False): return
    old_start=getattr(B,"start",None)
    if callable(old_start):
        async def persian_start(update,context):
            uid=update.effective_user.id; B.S.setdefault(uid,{})["lang"]="fa"
            return await old_start(update,context)
        B.start=persian_start
    B._persian_24x7_lock_installed=True
