"""Final Rubika routing guard.

The webhook layer used to translate numeric ChatKeypad button IDs into labels
before calling the legacy handler. Several legacy handlers route by numeric ID,
so that translation made valid buttons appear dead, especially in the foreign
main menu, partner panel and admin panel. This guard keeps IDs intact and only
normalizes presentation labels.
"""
import logging
log = logging.getLogger("netyar.rubika_final_router")


def _clean_rows(rows):
    out = []
    for row in rows or []:
        rr = []
        for item in row or []:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                bid, label = str(item[0]), str(item[1])
            else:
                bid, label = "0", str(item)
            for p in ("🔵 ", "🟦 ", "🟩 ", "🟨 "):
                if label.startswith(p):
                    label = label[len(p):].strip()
            rr.append((bid, label))
        if rr:
            out.append(rr)
    return out


def install():
    try:
        import server
        import rubika_v2 as rb

        # Keep the webhook's numeric button IDs. The legacy handler was written
        # around these IDs; converting them to visible labels broke routing.
        server._normalize_rubika_button = lambda update, _rb: update

        # server._patch_rubika is called for every webhook after startup and used
        # to overwrite the full menu. Wrap it so the canonical menu is restored
        # after that compatibility patch has run.
        old_patch = getattr(server, "_patch_rubika", None)
        if old_patch and not getattr(server, "_netyar_final_router_patch", False):
            def patch(r):
                result = old_patch(r)
                # Canonical foreign main menu: stable IDs + clean labels.
                def main_rows(uid):
                    lang = r.STATE.get(str(uid), {}).get("lang", "fa")
                    if lang == "en":
                        rows = [[("1", "FIDA non-in-person"), ("2", "Printing")],
                                [("3", "Government access issue"), ("4", "Tracking")],
                                [("5", "SIM services"), ("6", "Screening & follow-up")],
                                [("7", "My wallet"), ("8", "Partner panel")],
                                [("9", "Contact us"), ("10", "Start again")]]
                    elif lang == "ar":
                        rows = [[("1", "خدمة فيدا"), ("2", "الطباعة")],
                                [("3", "مشكلة خدمات الحكومة"), ("4", "متابعة")],
                                [("5", "خدمات الشريحة"), ("6", "الفحص والمتابعة")],
                                [("7", "محفظتي"), ("8", "لوحة الشركاء")],
                                [("9", "اتصل بنا"), ("10", "بدء من جديد")]]
                    else:
                        rows = [[("1", "🪪 فیدای غیر حضوری"), ("2", "🖨 خدمات چاپ")],
                                [("3", "🏛 حل مشکل ورود اتباع دولت من"), ("4", "🎫 پیگیری")],
                                [("5", "📱 خدمات سیم کارت"), ("6", "📝 آزمون غربالگری و پیگیری")],
                                [("7", "💰 کیف پول من"), ("8", "👥 پنل همکاران")],
                                [("9", "📞 تماس با ما"), ("10", "🔄 شروع مجدد")]]
                    return rows
                r.main_rows = main_rows

                # Make restart and the two panel entries unambiguous even when
                # a legacy wrapper receives the visible text instead of the ID.
                if not getattr(r, "_netyar_final_handle_router", False):
                    previous = r.handle
                    def handle(uid, chat, x, u):
                        text = str(x or "").strip()
                        st = r.STATE.setdefault(str(uid), {})
                        step = st.get("step", "")
                        aliases = {
                            "🔄 شروع مجدد": "10", "Start again": "10", "Restart": "10", "بدء من جديد": "10",
                            "👥 پنل همکاران": "8", "Partner panel": "8", "لوحة الشركاء": "8",
                            "🎫 پیگیری": "4", "Tracking": "4", "المتابعة": "4",
                            "🛠 پنل مدیریت بات": "admin", "Admin panel": "admin", "لوحة الإدارة": "admin",
                        }
                        if text in aliases:
                            text = aliases[text]
                        if text == "10":
                            lang = st.get("lang", "fa")
                            citizenship = st.get("citizenship") or st.get("status")
                            r.STATE[str(uid)] = {"lang": lang}
                            if citizenship:
                                r.STATE[str(uid)]["citizenship"] = citizenship
                                r.STATE[str(uid)]["status"] = citizenship
                            r.STATE[str(uid)]["step"] = "language"
                            return r.send(chat, r.TEXT[lang]["lang"], [[("1", "🇮🇷 فارسی"), ("2", "🇬🇧 English"), ("3", "🇸🇦 العربية")]])
                        return previous(uid, chat, text, u)
                    r.handle = handle
                    r._netyar_final_handle_router = True
                return result
            server._patch_rubika = patch
            server._netyar_final_router_patch = True
    except Exception:
        log.exception("Rubika final button router installation failed")
