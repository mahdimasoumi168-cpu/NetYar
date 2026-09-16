        V31.install(app,B)
        log.info("REAL runtime: partner runtime fix v31 installed")
    except Exception:log.exception("partner runtime fix v31 unavailable")
    try:
        import telegram_partner_final_router_v29 as V29
        V29.install(app,B)
        log.info("REAL runtime: partner router v29 installed")
    except Exception:log.exception("partner final router v29 unavailable")
    try:
        import telegram_absolute_callback_hardening_v30 as V30
        V30.install(app,B)
        log.info("REAL runtime: absolute callback hardening v30 installed")
    except Exception:log.exception("absolute callback hardening v30 unavailable")
    try:
        import telegram_management_only_v32 as V32
        V32.install(app,B)
        log.info("REAL runtime: management-only partner UI v32 installed")
    except Exception:log.exception("management-only v32 unavailable")
    try:
        import telegram_session_and_context_hardening_v33 as V33
        V33.install(app,B)
        log.info("REAL runtime: session/context hardening v33 installed")
    except Exception:log.exception("session/context hardening v33 unavailable")
    # Final deterministic admin navigation: exposes «➕ افزودن همکار جدید»
    # inside the real management panel, not only in an unused loader.
    try:
        import telegram_final_admin_navigation_v3 as AN
        await AN.install(app,B)
        log.info("REAL runtime: final admin navigation v3 installed")
    except Exception:log.exception("final admin navigation v3 unavailable")
    # Final partner navigation: always re-authenticate on panel entry and keep
    # cancel/back actions inside the partner panel context.
    try:
        import telegram_partner_navigation_final_v33 as PN
        PN.install(app,B)
        log.info("REAL runtime: partner navigation v33 installed")
    except Exception:log.exception("partner navigation v33 unavailable")
    if getattr(B,"_partner_final_router_v29",False) and getattr(B,"_absolute_callback_v30",False):
        log.info("REAL runtime final layers OK: v29 + v30 + v33")
    else:
        log.error("REAL runtime final layers FAILED: v29=%s v30=%s v33=%s",getattr(B,"_partner_final_router_v29",False),getattr(B,"_absolute_callback_v30",False),getattr(B,"_session_context_hardening_v33",False))
    B.start=_start
    app.add_handler(CommandHandler("start",_start),group=-10000000)
    app.add_handler(MessageHandler(filters.Regex(r"^🔄 شروع مجدد$"),_restart),group=-9999999)
    app.add_handler(CallbackQueryHandler(_blocked_language_callback,pattern=r"^(lang|language):"),group=-9999998)
    app.add_handler(CallbackQueryHandler(_services_callback,pattern=r"^start:services$"),group=-9999997)
    log.info("Telegram Persian-only authoritative startup handlers installed")

def _self_check():
    required=("main","partner","fida","gov","prt","ptrack","phistory","media","router","admin","cancel")
    missing=[name for name in required if not callable(getattr(B,name,None))]
    if missing:log.error("Telegram runtime self-check FAILED; missing hooks: %s",missing)

def build():
    token=str(getattr(B,"BOT_TOKEN","") or "").strip()
    if not token:raise RuntimeError("Telegram bot token is missing")