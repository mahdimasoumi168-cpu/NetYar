"""Final Telegram admin/navigation/text-control layer.

Installed last so it becomes the deterministic owner of:
- complete admin exit
- add partner
- sequential per-partner pricing
- centralized text/button overrides

This layer is additive and does not remove legacy service handlers.
"""
import hashlib
import re
from datetime import datetime, timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, MessageHandler, filters, ApplicationHandlerStop


def _now():
    return datetime.now(timezone.utc).isoformat()


def _digits(v):
    return str(v or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _ensure(B):
    B.db.conn.execute("CREATE TABLE IF NOT EXISTS telegram_text_overrides (key TEXT PRIMARY KEY, original TEXT NOT NULL DEFAULT '', value TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT 'text', updated_at TEXT NOT NULL)")
    B.db.conn.commit()


def _key(text, kind="text"):
    raw=f"{kind}|{str(text or '').strip()}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]


def _get(B, text, kind="text"):
    k=_key(text,kind)
    r=B.db.conn.execute("SELECT value FROM telegram_text_overrides WHERE key=?",(k,)).fetchone()
    return str(r["value"]) if r and r["value"] else str(text or "")


def _set(B, original, value, kind="text"):
    k=_key(original,kind)
    B.db.conn.execute("INSERT OR REPLACE INTO telegram_text_overrides(key,original,value,kind,updated_at) VALUES(?,?,?,?,?)",(k,str(original or ''),str(value or ''),kind,_now()))
    B.db.conn.commit()


def _apply_markup(B, markup):
    if markup is None or not hasattr(markup,"inline_keyboard"):
        return markup
    rows=[]
    for row in markup.inline_keyboard:
        nr=[]
        for b in row:
            label=str(getattr(b,"text","") or "")
            if label:
                try: label=_get(B,label,"button")
                except Exception: pass
            nr.append(InlineKeyboardButton(label,url=getattr(b,"url",None),callback_data=getattr(b,"callback_data",None),web_app=getattr(b,"web_app",None)))
        rows.append(nr)
    return InlineKeyboardMarkup(rows)


def _clear_admin_session(B, uid):
    old=dict(B.S.get(uid,{})); keep={k:old[k] for k in ("lang","status","citizenship") if k in old}
    B.S[uid]=keep
    return keep


def _admin_menu_patch(A,B):
    old=A._admin_menu
    def menu():
        m=old()
        rows=[list(r) for r in m.inline_keyboard]
        # Remove duplicate legacy special-pricing buttons and add canonical controls once.
        rows=[r for r in rows if not any("کاهش/افزایش قیمت همکار خاص" in str(getattr(x,"text","")) for x in r)]
        if not any(any(str(getattr(x,"text",""))=="➕ افزودن همکار جدید" for x in r) for r in rows):
            rows.insert(1,[("➕ افزودن همکار جدید","adm:addpartner")])
        if not any(any(str(getattr(x,"text",""))=="📈 قیمت‌گذاری تک‌تک خدمات همکار" for x in r) for r in rows):
            rows.insert(6,[("📈 قیمت‌گذاری تک‌تک خدمات همکار","ppx:start")])
        if not any(any(str(getattr(x,"text",""))=="🚪 خروج کامل از مدیریت" for x in r) for r in rows):
            rows.append([( "🚪 خروج کامل از مدیریت", "adm:exit")])
        return _apply_markup(B,InlineKeyboardMarkup(rows))
    A._admin_menu=menu
    return old


def _texts_menu(B):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👋 استارت و خوش‌آمد",callback_data="txe:welcome"),InlineKeyboardButton("🌐 زبان‌ها",callback_data="txe:language")],
        [InlineKeyboardButton("👤 منوی مشترکین",callback_data="txe:customer_menu"),InlineKeyboardButton("👥 پنل همکاران",callback_data="txe:partner_menu")],
        [InlineKeyboardButton("🛠 پنل مدیریت",callback_data="txe:admin_menu"),InlineKeyboardButton("📝 متن‌های اطلاعات‌گیری",callback_data="txe:inputs")],
        [InlineKeyboardButton("🔘 ویرایش نام دکمه",callback_data="txe:button")],
        [InlineKeyboardButton("⬅️ پنل مدیریت",callback_data="txe:back")],
    ])


def install(app,B):
    _ensure(B)
    import telegram_admin_plus as A
    _admin_menu_patch(A,B)

    # Patch UI.inline so edited button labels keep their original callback_data.
    try:
        import telegram_ui_policy_v2 as UI
        if not getattr(UI,"_text_control_wrapped",False):
            old_inline=UI.inline
            def inline(rows,*args,**kwargs):
                return _apply_markup(B,old_inline(rows,*args,**kwargs))
            UI.inline=inline
            UI._text_control_wrapped=True
    except Exception:
        pass

    # Patch current main/partner keyboards after every legacy layer has finished.
    for attr in ("main","partner_kb"):
        old=getattr(B,attr,None)
        if callable(old) and not getattr(B,f"_text_control_{attr}",False):
            def make(oldfn):
                def wrapped(*args,**kwargs):
                    return _apply_markup(B,oldfn(*args,**kwargs))
                return wrapped
            setattr(B,attr,make(old));setattr(B,f"_text_control_{attr}",True)

    old_cb=A._callback
    old_text=A._text

    async def admin_callback(update,context,Bot):
        q=update.callback_query; data=str(q.data or "") if q else ""
        if not data.startswith("adm:"):
            return await old_cb(update,context,Bot)
        action=data.split(":",1)[1]
        uid=q.from_user.id
        if action=="exit":
            await q.answer()
            _clear_admin_session(B,uid)
            return await q.message.reply_text("✅ از پنل مدیریت به‌طور کامل خارج شدید.",reply_markup=B.main(uid))
        if action=="addpartner":
            await q.answer()
            st=B.S.setdefault(uid,{})
            st.update(admin_plus_mode="power_add_name",power_partner={})
            return await q.message.reply_text("➕ افزودن همکار جدید\n\n👤 نام و نام خانوادگی یا نام مجموعه همکار را وارد کنید:",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ انصراف",callback_data="adm:menu")]]))
        if action=="texts":
            await q.answer()
            return await q.message.reply_text("✏️ مرکز ویرایش متن و دکمه‌ها\n\nاز اینجا می‌توانید متن‌های اصلی و نام دکمه‌های ربات را تغییر دهید. تغییر نام دکمه فقط ظاهر آن را عوض می‌کند و کاربرد دکمه ثابت می‌ماند.",reply_markup=_texts_menu(B))
        return await old_cb(update,context,Bot)

    async def admin_text(update,context,Bot):
        uid=update.effective_user.id; st=B.S.setdefault(uid,{})
        mode=st.get("admin_plus_mode")
        t=(update.message.text or "").strip()
        if mode=="power_add_name":
            if len(t)<2:return await update.message.reply_text("❌ نام معتبر وارد کنید.")
            st["power_partner"]["name"]=t;st["admin_plus_mode"]="power_add_phone"
            return await update.message.reply_text("📱 شماره موبایل اختصاصی همکار را وارد کنید:")
        if mode=="power_add_phone":
            p=re.sub(r"\D","",_digits(t))
            if p.startswith("98"):p="0"+p[2:]
            if not re.fullmatch(r"09\d{9}",p):return await update.message.reply_text("❌ شماره موبایل معتبر نیست. مثال: 09123456789")
            exists=B.db.conn.execute("SELECT 1 FROM partners WHERE phone=?",(p,)).fetchone()
            if exists:return await update.message.reply_text("❌ این شماره قبلاً به‌عنوان همکار ثبت شده است.")
            st["power_partner"]["phone"]=p;st["admin_plus_mode"]="power_add_password"
            return await update.message.reply_text("🔐 رمز ورود همکار را وارد کنید (حداقل ۴ رقم/حرف):")
        if mode=="power_add_password":
            if len(t)<4:return await update.message.reply_text("❌ رمز باید حداقل ۴ کاراکتر باشد.")
            from core import hash_password
            p=st["power_partner"]
            B.db.conn.execute("INSERT INTO partners(phone,password_hash,name,active,balance,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",(p["phone"],hash_password(t),p["name"],1,0,B.now(),B.now()))
            B.db.conn.commit(); row=B.db.conn.execute("SELECT id FROM partners WHERE phone=?",(p["phone"],)).fetchone()
            st["admin_plus_mode"]=None;st.pop("power_partner",None)
            return await update.message.reply_text(f"✅ همکار جدید با موفقیت فعال شد.\n\n👤 {p['name']}\n📱 {p['phone']}\n🆔 شناسه: {row['id'] if row else '-'}\n💰 موجودی اولیه: 0 تومان",reply_markup=A._admin_menu())
        if mode in {"text","announce","price_delta","price_set","credit_partner","credit_amount"}:
            return await old_text(update,context,Bot)
        return None

    A._callback=admin_callback
    A._text=admin_text

    # Sequential partner pricing: one partner, then every service in DB, one price at a time.
    async def ppx_cb(update,context):
        q=update.callback_query; data=str(q.data or "") if q else ""
        if data!="ppx:start" or not B.admin(q.from_user.id):return
        await q.answer(); uid=q.from_user.id; st=B.S.setdefault(uid,{})
        st["ppx_mode"]="partner";st.pop("ppx_data",None)
        return await q.message.reply_text("📈 قیمت‌گذاری تک‌تک خدمات برای یک همکار\n\n👤 شناسه یا شماره موبایل همکار را وارد کنید:")

    async def ppx_text(update,context):
        uid=update.effective_user.id;st=B.S.setdefault(uid,{})
        mode=st.get("ppx_mode");t=(update.message.text or "").strip()
        if not mode:return
        if t in {"لغو","انصراف","❌ انصراف"}:
            st.pop("ppx_mode",None);st.pop("ppx_data",None)
            return await update.message.reply_text("لغو شد.",reply_markup=A._admin_menu())
        if mode=="partner":
            v=_digits(t); p=None
            if v.isdigit(): p=B.db.conn.execute("SELECT * FROM partners WHERE id=? OR phone=? LIMIT 1",(int(v),v)).fetchone()
            else:p=B.db.conn.execute("SELECT * FROM partners WHERE phone=? OR name LIKE ? LIMIT 1",(v,f"%{v}%")).fetchone()
            if not p:return await update.message.reply_text("❌ همکار پیدا نشد. دوباره شناسه یا شماره را وارد کنید.")
            services=B.db.conn.execute("SELECT key,name,price FROM services ORDER BY id").fetchall()
            if not services:return await update.message.reply_text("❌ هیچ خدمتی برای قیمت‌گذاری ثبت نشده است.",reply_markup=A._admin_menu())
            st["ppx_data"]={"partner_id":int(p["id"]),"name":p["name"] or "-","services":[dict(r) for r in services],"i":0,"prices":{}};st["ppx_mode"]="price"
            r=services[0]
            return await update.message.reply_text(f"👤 همکار: {p['name'] or '-'} | 📱 {p['phone']}\n\n1/{len(services)}\n💰 قیمت «{r['name']}» را به تومان وارد کنید:")
        if mode=="price":
            raw=re.sub(r"[٬,\s]","",_digits(t))
            if not raw.isdigit():return await update.message.reply_text("❌ فقط عدد وارد کنید؛ مثال: 400000")
            d=st["ppx_data"];r=d["services"][d["i"]];d["prices"][r["key"]]=int(raw)
            d["i"]+=1
            if d["i"]<len(d["services"]):
                n=d["services"][d["i"]]
                return await update.message.reply_text(f"{d['i']+1}/{len(d['services'])}\n💰 قیمت «{n['name']}» را به تومان وارد کنید:")
            for k,v in d["prices"].items():
                B.db.conn.execute("INSERT OR REPLACE INTO partner_service_prices(partner_id,service_key,price,updated_at) VALUES(?,?,?,?)",(d["partner_id"],k,v,_now()))
            B.db.conn.commit(); summary="\n".join(f"• {x['name']}: {d['prices'][x['key']]:,} تومان" for x in d["services"])
            st.pop("ppx_mode",None);st.pop("ppx_data",None)
            return await update.message.reply_text(f"✅ قیمت تمام خدمات برای «{d['name']}» ثبت شد.\n\n{summary}",reply_markup=A._admin_menu())

    app.add_handler(CallbackQueryHandler(ppx_cb,pattern=r"^ppx:start$"),group=-10001)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,ppx_text),group=-10001)

    # Text/button editor callbacks.
    async def txe_cb(update,context):
        q=update.callback_query;data=str(q.data or "") if q else ""
        if not data.startswith("txe:") or not B.admin(q.from_user.id):return
        await q.answer();uid=q.from_user.id;st=B.S.setdefault(uid,{})
        action=data.split(":",1)[1]
        if action=="back":return await q.message.reply_text("🛠 پنل مدیریت",reply_markup=A._admin_menu())
        if action=="button":
            st["txe_mode"]="button_old";return await q.message.reply_text("🔘 متن فعلی دکمه را دقیقاً ارسال کنید:")
        presets={
            "welcome":("👋 متن خوش‌آمدگویی استارت","👋 سلام!\n\nبه سامانه خدمات آنلاین بات، کمک یار مهاجر خوش آمدید. 🌟\n\nلطفاً زبان را انتخاب کنید."),
            "language":("🌐 متن انتخاب زبان","لطفاً زبان را انتخاب کنید."),
            "customer_menu":("👤 عنوان منوی مشترکین","منوی خدمات کمک یار مهاجر 👇"),
            "partner_menu":("👥 عنوان پنل همکاران","👥 پنل همکاران"),
            "admin_menu":("🛠 عنوان پنل مدیریت","🛠 پنل مدیریت کامل"),
            "inputs":("📝 متن مرحله‌های اطلاعات‌گیری","متن مرحله اطلاعات‌گیری را از منوی ویرایش دکمه‌ها تغییر دهید."),
        }
        if action in presets:
            title,default=presets[action];st["txe_mode"]="text";st["txe_original"]=default
            cur=_get(B,default,"text")
            return await q.message.reply_text(f"{title}\n\nمتن فعلی:\n{cur}\n\nمتن جدید را ارسال کنید:")

    async def txe_text(update,context):
        uid=update.effective_user.id;st=B.S.setdefault(uid,{})
        mode=st.get("txe_mode");t=(update.message.text or "").strip()
        if not mode:return
        if mode=="text":
            _set(B,st.get("txe_original",""),t,"text");st.pop("txe_mode",None);st.pop("txe_original",None)
            return await update.message.reply_text("✅ متن ذخیره شد و در رندرهای مرکزی بعدی استفاده می‌شود.",reply_markup=_texts_menu(B))
        if mode=="button_old":
            st["txe_button_old"]=t;st["txe_mode"]="button_new"
            return await update.message.reply_text(f"🔘 متن جدید برای دکمه «{t}» را ارسال کنید:")
        if mode=="button_new":
            old=st.get("txe_button_old","");_set(B,old,t,"button");st.pop("txe_mode",None);st.pop("txe_button_old",None)
            return await update.message.reply_text("✅ نام دکمه ذخیره شد. کاربرد و callback دکمه تغییر نکرد.",reply_markup=_texts_menu(B))

    app.add_handler(CallbackQueryHandler(txe_cb,pattern=r"^txe:"),group=-10002)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,txe_text),group=-10002)

    # Make the final admin menu use the edited labels too.
    B.amenu=A._admin_menu
    B._admin_power_installed=True
