"""Rubika side of the durable admin control center.

Every visible admin option has a concrete route. The panel is deliberately
DB-backed so prices, services, texts, partners, requests and reports can be
managed without editing source code.
"""
import logging
from admin_control_v5 import get, put, set_service, service_rows, ensure
log = logging.getLogger("netyar.rubika_admin_v5")
DONE = False


def _fmt_rows(rows, limit=12):
    out = []
    for r in rows[:limit]:
        vals = []
        for k in r.keys():
            v = r[k]
            if k in {"password_hash", "token_ref", "receipt_file_id"}:
                continue
            vals.append(f"{k}={v}")
        out.append("• " + " | ".join(vals))
    return "\n".join(out) or "— موردی وجود ندارد."


def install():
    global DONE
    if DONE:
        return
    ensure()
    try:
        import rubika_v2 as R
        old_admin = getattr(R, "admin", None)

        def rows():
            return [
                [("1", "👥 کاربران"), ("2", "🤝 همکاران")],
                [("3", "📋 درخواست‌ها"), ("4", "💰 شارژها")],
                [("5", "🟢/🔴 خدمات ایرانی"), ("6", "🟢/🔴 خدمات اتباع")],
                [("7", "💰 قیمت خدمات"), ("8", "📝 تغییر متن‌ها")],
                [("9", "🤖 مدیریت پیام‌رسان‌ها"), ("10", "👤 مدیران")],
                [("11", "📊 گزارش‌ها"), ("12", "🎫 تیکت‌ها")],
                [("13", "📎 مدارک و فایل‌ها"), ("14", "🔄 همگام‌سازی")],
                [("19", "📈 قیمت ویژه همکار خاص")],
                [("15", "🔄 شروع مجدد")],
                [("16", "📞 پشتیبانی"), ("17", "⚙️ تنظیمات پایه")],
                [("0", "⬅️ منوی اصلی")],
            ]
        R.admin_rows = rows

        def admin(uid, chat, x):
            uid = str(uid)
            st = R.STATE.setdefault(uid, {})
            x = str(x or "").strip()
            step = st.get("step", "")

            # Navigation must always work, regardless of the current sub-flow.
            if x in {"15", "99", "🔄 شروع مجدد", "شروع مجدد"}:
                lang = st.get("lang", "fa")
                st.clear()
                st.update({"lang": lang, "step": "admin"})
                return R.send(chat, "🛠 پنل مدیریت\nگزینه موردنظر را انتخاب کنید:", rows())
            if x in {"0", "⬅️ منوی اصلی"}:
                st["step"] = "menu"
                return R.send(chat, "🏠 منوی اصلی", R.main_rows(uid))

            # Concrete overview panels.
            if x == "1":
                st["step"] = "admin"
                rs = R.db.conn.execute("SELECT id,platform,external_id,username,full_name,phone,created_at FROM users ORDER BY id DESC LIMIT 12").fetchall()
                return R.send(chat, "👥 آخرین کاربران\n\n" + _fmt_rows(rs), rows())
            if x == "2":
                st["step"] = "admin"
                rs = R.db.conn.execute("SELECT id,name,phone,balance,active,created_at FROM partners ORDER BY id DESC LIMIT 12").fetchall()
                return R.send(chat, "🤝 همکاران\n\n" + _fmt_rows(rs), rows())
            if x == "3":
                st["step"] = "admin"
                rs = R.db.conn.execute("SELECT id,tracking_code,service_key,platform,status,amount,payment_status,created_at FROM requests ORDER BY id DESC LIMIT 12").fetchall()
                return R.send(chat, "📋 آخرین درخواست‌ها\n\n" + _fmt_rows(rs), rows())
            if x == "4":
                st["step"] = "admin"
                rs = R.db.conn.execute("SELECT id,partner_id,amount,status,created_at,reviewed_at,note FROM topups ORDER BY id DESC LIMIT 12").fetchall()
                return R.send(chat, "💰 آخرین شارژها\n\n" + _fmt_rows(rs), rows())
            if x == "10":
                st["step"] = "admin"
                rs = R.db.conn.execute("SELECT platform,external_id,role,active FROM admins ORDER BY platform,external_id").fetchall()
                return R.send(chat, "👤 مدیران\n\n" + _fmt_rows(rs), rows())
            if x == "11":
                st["step"] = "admin"
                users = R.db.conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
                partners = R.db.conn.execute("SELECT COUNT(*) c FROM partners WHERE active=1").fetchone()["c"]
                requests = R.db.conn.execute("SELECT COUNT(*) c FROM requests").fetchone()["c"]
                pending = R.db.conn.execute("SELECT COUNT(*) c FROM requests WHERE status NOT IN ('done','completed','cancelled')").fetchone()["c"]
                topups = R.db.conn.execute("SELECT COUNT(*) c FROM topups WHERE status='pending'").fetchone()["c"]
                return R.send(chat, f"📊 گزارش کلی\n\n👥 کاربران: {users}\n🤝 همکاران فعال: {partners}\n📋 درخواست‌ها: {requests}\n⏳ درخواست‌های باز: {pending}\n💰 شارژهای در انتظار: {topups}", rows())
            if x == "13":
                st["step"] = "admin"
                rs = R.db.conn.execute("SELECT request_id,field_key,file_id,created_at FROM request_answers WHERE file_id<>'' ORDER BY id DESC LIMIT 15").fetchall()
                return R.send(chat, "📎 مدارک و فایل‌های ثبت‌شده\n\n" + _fmt_rows(rs), rows())
            if x == "14":
                st["step"] = "admin"
                return R.send(chat, "🔄 همگام‌سازی انجام شد.\n\nپایگاه‌داده و تنظیمات جاری از منبع اصلی خوانده می‌شوند.", rows())
            if x == "9":
                st["step"] = "admin"
                rs = R.db.conn.execute("SELECT platform,bot_name,active,status,updated_at FROM bot_integrations ORDER BY id DESC").fetchall()
                return R.send(chat, "🤖 پیام‌رسان‌ها / بات‌ها\n\n" + _fmt_rows(rs), rows())

            # Full service controls.
            if x == "6":
                st["step"] = "admin_service_foreign"
                return R.send(chat, "🇦🇫 خدمات اتباع\nکلید خدمت را ارسال کنید؛ مثال: fida", [[("15", "🔄 شروع مجدد")]])
            if x == "5":
                st["step"] = "admin_service_iranian"
                return R.send(chat, "🇮🇷 خدمات ایرانی\nکلید خدمت را ارسال کنید.", [[("15", "🔄 شروع مجدد")]])
            if x == "7":
                st["step"] = "admin_price"
                services = R.db.conn.execute("SELECT key,name,price,active FROM services ORDER BY id").fetchall()
                text = "💰 قیمت خدمات\n\n" + "\n".join(f"• {r['key']} — {r['name']} — {int(r['price'] or 0):,} تومان — {'فعال' if r['active'] else 'غیرفعال'}" for r in services)
                return R.send(chat, text + "\n\nکلید خدمت را ارسال کنید:", [[("15", "🔄 شروع مجدد")]])
            if x == "8":
                st["step"] = "admin_text"
                return R.send(chat, "📝 کلید متن را ارسال کنید.\nمثال: welcome_fa / support_text / restart_text / disabled_text", [[("15", "🔄 شروع مجدد")]])
            if x in {"16", "📞 پشتیبانی"}:
                st["step"] = "admin_support"
                return R.send(chat, f"📞 پشتیبانی فعلی: {get('support_id','@Good_ok_2000')}\nشناسه جدید را ارسال کنید.", [[("15", "🔄 شروع مجدد")]])
            if x == "17":
                st["step"] = "admin_base"
                return R.send(chat, "⚙️ تنظیمات پایه: support / restart / disabled\nکلید را ارسال کنید.", [[("15", "🔄 شروع مجدد")]])
            if x == "19":
                # partner_pricing owns the detailed conversation; delegation is
                # intentional so its partner/service price state is preserved.
                if old_admin:
                    return old_admin(uid, chat, x)

            # Sub-flows.
            if step in {"admin_service_foreign", "admin_service_iranian"}:
                r = R.db.conn.execute("SELECT key,name,active FROM services WHERE key=?", (x,)).fetchone()
                if not r:
                    return R.send(chat, "❌ کلید خدمت پیدا نشد. دوباره ارسال کنید.")
                group = "iranian" if step.endswith("iranian") else "foreign"
                set_service(x, not bool(r["active"]), group=group)
                st["step"] = "admin"
                return R.send(chat, ("🟢 فعال شد: " if not r["active"] else "🔴 بسته شد: ") + r["name"], rows())
            if step == "admin_price":
                r = R.db.conn.execute("SELECT key,name,price FROM services WHERE key=?", (x,)).fetchone()
                if not r:
                    return R.send(chat, "❌ خدمت پیدا نشد.")
                st["price_key"] = x; st["step"] = "admin_price_value"
                return R.send(chat, f"💰 قیمت فعلی {r['name']}: {int(r['price'] or 0):,} تومان\nمبلغ جدید را عددی بفرستید.")
            if step == "admin_price_value":
                if not x.isdigit():
                    return R.send(chat, "❌ فقط عدد وارد کنید.")
                set_service(st["price_key"], price=int(x)); st["step"] = "admin"
                return R.send(chat, "✅ قیمت ذخیره شد.", rows())
            if step == "admin_text":
                st["text_key"] = x; st["step"] = "admin_text_value"
                return R.send(chat, f"📝 متن فعلی:\n{get(x,'')}\n\nمتن جدید را ارسال کنید.")
            if step == "admin_text_value":
                put(st["text_key"], x); st["step"] = "admin"
                return R.send(chat, "✅ متن ذخیره شد.", rows())
            if step == "admin_support":
                v = x if x.startswith("@") else "@" + x
                put("support_id", v); put("support_text", "📞 پشتیبانی: " + v); st["step"] = "admin"
                return R.send(chat, "✅ پشتیبانی ذخیره شد.", rows())
            if step == "admin_base":
                if x not in {"support", "restart", "disabled"}:
                    return R.send(chat, "❌ کلید نامعتبر است.")
                st["base_key"] = x; st["step"] = "admin_base_value"
                return R.send(chat, f"مقدار فعلی: {get(x+'_text',get(x,''))}\nمقدار جدید را ارسال کنید.")
            if step == "admin_base_value":
                k = st.get("base_key")
                put(k + "_text" if k in {"restart", "disabled"} else k, x); st["step"] = "admin"
                return R.send(chat, "✅ تنظیم ذخیره شد.", rows())

            if old_admin:
                return old_admin(uid, chat, x)
            return R.send(chat, "🛠 پنل مدیریت", rows())

        R.admin = admin
    except Exception:
        log.exception("rubika admin control v5 failed")
    DONE = True
