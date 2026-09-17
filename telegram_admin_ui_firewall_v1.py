"""Final admin UI firewall.

The project has accumulated many historical admin layers. Several of them
create their own menu builders, so replacing only telegram_admin_plus._admin_menu
is insufficient. This module runs after every Telegram layer and rebinds only
functions that clearly contain admin-panel labels.
"""
import inspect
import logging
import sys

log = logging.getLogger("netyar.admin.firewall")

_ADMIN_NAMES = {
    "_admin_menu", "admin_menu", "build_admin_menu", "admin_panel_menu",
    "management_menu", "admin_kb", "admin_keyboard",
}
_MARKERS = (
    "پنل مدیریت", "مدیریت درخواست", "شارژها", "پرداخت‌ها",
    "افزایش قیمت", "کاهش قیمت", "پنل کاربران", "همکاران",
)


def _looks_admin(fn):
    try:
        src = inspect.getsource(fn)
    except Exception:
        return False
    return any(x in src for x in _MARKERS)


def install(app, B):
    canonical = __import__("telegram_canonical_admin_final")
    menu = canonical.menu
    B.amenu = menu
    B.admin_menu_final = menu
    changed = []

    # Always restore the primary legacy owner.
    try:
        import telegram_admin_plus as A
        A._admin_menu = menu
        changed.append("telegram_admin_plus._admin_menu")
    except Exception:
        pass

    # Rebind admin menu builders in every already-loaded NetYar Telegram
    # layer. Customer/service menus are left untouched unless their function
    # source explicitly contains the admin-panel markers above.
    for modname, mod in list(sys.modules.items()):
        if not modname or not (modname.startswith("telegram_") or modname in {
            "full_admin_control_patch", "production_final_patch", "button_routing_fix"
        }):
            continue
        try:
            for attr, value in list(vars(mod).items()):
                if attr not in _ADMIN_NAMES or not callable(value) or value is menu:
                    continue
                if _looks_admin(value):
                    setattr(mod, attr, menu)
                    changed.append(f"{modname}.{attr}")
        except Exception:
            continue

    # Make the state observable in logs so deployment/runtime verification can
    # prove that this final layer actually executed.
    B._admin_ui_firewall_v1 = True
    B._admin_ui_firewall_rebound = tuple(changed)
    log.info("ADMIN UI FIREWALL active: canonical menu rebound across %d legacy builders", len(changed))
    return True
