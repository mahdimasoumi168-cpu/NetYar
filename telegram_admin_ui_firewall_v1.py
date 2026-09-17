"""Final admin UI firewall."""
import inspect, logging, sys
log=logging.getLogger("netyar.admin.firewall")
_ADMIN_NAMES={"_admin_menu","admin_menu","build_admin_menu","admin_panel_menu","management_menu","admin_kb","admin_keyboard","amenu","full_amenu","advanced_amenu","restored_menu"}
_MARKERS=("پنل مدیریت","مدیریت درخواست","شارژها","پرداخت‌ها","افزایش قیمت","کاهش قیمت","پنل کاربران","همکاران")
def _looks_admin(fn):
    try: src=inspect.getsource(fn)
    except Exception: return False
    return any(x in src for x in _MARKERS)
def install(app,B):
    canonical=__import__("telegram_canonical_admin_final"); menu=canonical.menu; changed=[]
    try:
        import bot; bot.amenu=menu; bot.admin_menu_final=menu; changed.append("bot.amenu")
    except Exception as exc: log.exception("Could not lock bot.amenu: %s",exc)
    B.amenu=menu; B.admin_menu_final=menu
    try:
        import telegram_admin_plus as A; A._admin_menu=menu; changed.append("telegram_admin_plus._admin_menu")
    except Exception: pass
    for modname,mod in list(sys.modules.items()):
        if not modname or not (modname.startswith("telegram_") or modname in {"bot","admin_full_v6","full_admin_control_patch","production_final_patch","button_routing_fix"}): continue
        try:
            for attr,value in list(vars(mod).items()):
                if attr not in _ADMIN_NAMES or not callable(value) or value is menu: continue
                if _looks_admin(value): setattr(mod,attr,menu); changed.append(f"{modname}.{attr}")
        except Exception: continue
    B._admin_ui_firewall_v1=True; B._admin_ui_firewall_rebound=tuple(changed)
    try:
        import telegram_runtime_finalizer_v1 as F
        F.install(app,B)
    except Exception: log.exception("CRITICAL: runtime finalizer unavailable")
    log.info("ADMIN UI FIREWALL v2 active: canonical admin menu locked across %d builders",len(changed))
    return True
