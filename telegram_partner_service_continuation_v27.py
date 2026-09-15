"""Final partner-service continuation guard.

Keeps partner service buttons deterministic after the menu has been rebuilt by
later layers, synchronizes the Irancell price, and prevents an active partner
from falling back to the public menu while a service is collecting data.
"""
import logging
from telegram.ext import MessageHandler, filters

log = logging.getLogger("netyar.telegram.partner_continuation_v27")
IRANCELL = "📱 حل مشکل سیم کارت ایرانسل"
PRICE = 980_000


def _sync(B):
    try:
        B.db.conn.execute("UPDATE services SET price=?, active=1, description=? WHERE key=?", (PRICE, "حل مشکل سیم کارت ایرانسل از طریق پنل همکاران", "irancell_sim_issue"))
        B.db.conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", ("price_irancell_sim", str(PRICE)))
        B.db.conn.commit()
    except Exception:
        try: B.db.conn.rollback()
        except Exception: pass


def _kb(B, lang="fa"):
    try:
        import telegram_ui_policy_v2 as U
        return U.inline([
            ["➕ شارژ حساب", IRANCELL],
            ["🏛 حل مشکل سامانه دولت من", "🎫 درخواست‌های من"],
            ["📱 خدمات سیم کارت", "🪪 فیدای غیر حضوری"],
            ["🔎 پیگیری کد", "📋 سوابق"],
            ["💰 موجودی"],
            ["🎫 تیکت به مدیریت", "💬 ارتباط با مدیریت"],
            ["🚪 خروج از پنل"],
            ["❌ انصراف"],
        ], B)
    except Exception:
        try: return B.partner_kb(lang)
        except Exception: return None


def install(app, B):
    if getattr(B, "_partner_continuation_v27", False): return
    _sync(B)

    old = getattr(B, "partner_kb", None)
    def partner_kb(lang="fa"):
        try: return _kb(B, lang)
        except Exception:
            return old(lang) if callable(old) else None
    B.partner_kb = partner_kb

    B._partner_service_price = PRICE
    B._partner_continuation_v27 = True
    log.info("Partner continuation v27 installed; Irancell price=%s", PRICE)

    # Absolute final owner: this is intentionally installed after every
    # previous menu/callback overlay so legacy dispatchers cannot hide the
    # Irancell option or leak a generic ui2 callback error.
    try:
        from telegram_final_service_owner_v28 import install as install_v28
        install_v28(app, B)
    except Exception:
        log.exception("Final service owner v28 unavailable")
