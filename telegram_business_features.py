"""Stable Telegram business features.

Persistent reply keyboards, partner/admin ticket chat, and safe billing helpers.
No polling or lifecycle code lives here.
"""
import logging
import re
from datetime import datetime, timezone
from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import MessageHandler, CallbackQueryHandler, filters, ApplicationHandlerStop

log = logging.getLogger("netyar.telegram.features")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _ensure(B):
    B.db.conn.executescript("""
    CREATE TABLE IF NOT EXISTS partner_telegram_links(
      partner_id INTEGER PRIMARY KEY, telegram_user_id TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS tickets(
      id INTEGER PRIMARY KEY AUTOINCREMENT, partner_id INTEGER NOT NULL, admin_id TEXT, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ticket_messages(
      id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id INTEGER NOT NULL, sender_role TEXT NOT NULL, sender_id TEXT NOT NULL,
      kind TEXT NOT NULL, text TEXT, file_id TEXT, created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket ON ticket_messages(ticket_id,id);
    """)
    B.db.conn.commit()


def _persistent_kb(rows):
    return ReplyKeyboardMarkup(rows, resize_keyboard=True, one_time_keyboard=False, is_persistent=True)


def _partner_kb():
    return _persistent_kb([
        ["➕ شارژ حساب", "🏛 حل مشکل سامانه دولت من"],
        ["🔎 پیگیری کد", "📋 سوابق"],
        ["💰 موجودی", "🎫 تیکت به مدیریت"],
        ["🚪 خروج از پنل"], ["❌ انصراف"],
    ])


def _admin_reply_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("↩️ پاسخ مجدد", callback_data="tk:partners")]])


def _partner_reply_kb(tid):
    return InlineKeyboardMarkup([[InlineKeyboardButton("↩️ پاسخ به مدیریت", callback_data=f"tk:reply:{tid}")]])


def _ticket(B, pid):
    r = B.db.conn.execute("SELECT * FROM tickets WHERE partner_id=? AND status='open' ORDER BY id DESC LIMIT 1", (pid,)).fetchone()
    if r:
        return r
    cur = B.db.conn.execute("INSERT INTO tickets(partner_id,status,created_at,updated_at) VALUES(?,?,?,?)", (pid,'open',_now(),_now()))
    B.db.conn.commit()
    return B.db.conn.execute("SELECT * FROM tickets WHERE id=?", (cur.lastrowid,)).fetchone()


def _link(B, pid, uid):
    B.db.conn.execute("INSERT OR REPLACE INTO partner_telegram_links(partner_id,telegram_user_id,created_at,updated_at) VALUES(?,?,COALESCE((SELECT created_at FROM partner_telegram_links WHERE partner_id=?),?),?)", (pid,str(uid),pid,_now(),_now()))
    B.db.conn.commit()


def _partner_for_uid(B, uid):
    return B.db.conn.execute("SELECT p.* FROM partners p JOIN partner_telegram_links l ON l.partner_id=p.id WHERE l.telegram_user_id=? AND p.active=1", (str(uid),)).fetchone()


async def _send_ticket_prompt(update, B):
    uid=update.effective_user.id
    p=_partner_for_uid(B,uid) or B.db.conn.execute("SELECT * FROM partners WHERE id=?", (B.S.get(uid,{}).get('partner_id',-1),)).fetchone()
    if not p:
        await update.message.reply_text("❌ ابتدا وارد پنل همکاران شوید.", reply_markup=B.main(uid)); return
    _link(B,p['id'],uid); t=_ticket(B,p['id'])
    B.S.setdefault(uid,{})['mode']='ticket_partner'
    B.S[uid]['ticket_id']=t['id']
    await update.message.reply_text("🎫 چت با مدیریت فعال شد.\nهر متن، عکس، ویدیو یا ویسی که بفرستید برای مدیریت ارسال می‌شود.\nبرای خروج «❌ انصراف» را بزنید.", reply_markup=_partner_kb())


async def _callback(update, context, B):
    q=update.callback_query
    if not q: return
    d=(q.data or '').split(':')
    if not d or d[0] != 'tk': return
    if not B.admin(q.from_user.id) and not (len(d)>=3 and d[1]=='reply'):
        await q.answer('دسترسی ندارید', show_alert=True); return
    await q.answer()
    uid=q.from_user.id; st=B.S.setdefault(uid,{})
    if len(d)>=2 and d[1]=='partners' and B.admin(uid):
        rows=B.db.conn.execute("SELECT p.id,p.name,p.phone,t.id ticket_id FROM partners p LEFT JOIN tickets t ON t.partner_id=p.id AND t.status='open' ORDER BY p.id DESC LIMIT 50").fetchall()
        buttons=[]
        for r in rows:
            buttons.append([InlineKeyboardButton(f"👤 {r['name'] or r['phone']}", callback_data=f"tk:choose:{r['id']}")])
        return await q.message.reply_text("🎫 انتخاب همکار برای پیام:", reply_markup=InlineKeyboardMarkup(buttons or [[InlineKeyboardButton('هیچ همکار فعالی نیست',callback_data='tk:none')]]))
    if len(d)>=2 and d[1]=='choose' and B.admin(uid):
        pid=int(d[2]); t=_ticket(B,pid); st.update(mode='ticket_admin',ticket_id=t['id'],ticket_partner_id=pid)
        return await q.message.reply_text("✉️ چت با همکار فعال شد. هر متن، عکس، ویدیو یا ویس بفرستید برای همکار ارسال می‌شود.\nبرای پایان «❌ انصراف» را بزنید.")
    if len(d)>=3 and d[1]=='reply':
        tid=int(d[2]); r=B.db.conn.execute("SELECT * FROM tickets WHERE id=?",(tid,)).fetchone()
        if not r: return await q.message.reply_text('❌ تیکت پیدا نشد.')
        if B.admin(uid):
            st.update(mode='ticket_admin',ticket_id=tid,ticket_partner_id=r['partner_id'])
            return await q.message.reply_text('✉️ پاسخ مجدد فعال شد. پیام خود را بفرستید.')
        if str(B.S.get(uid,{}).get('partner_id')) != str(r['partner_id']): return await q.message.reply_text('❌ دسترسی ندارید.')
        st.update(mode='ticket_partner',ticket_id=tid)
        return await q.message.reply_text('✉️ پاسخ مجدد فعال شد. پیام خود را بفرستید.', reply_markup=_partner_kb())


async def _forward(update, context, B):
    msg=update.message
    if not msg: return
    uid=update.effective_user.id; st=B.S.setdefault(uid,{})
    mode=st.get('mode')
    if mode not in {'ticket_partner','ticket_admin'}: return
    tid=int(st.get('ticket_id') or 0)
    t=B.db.conn.execute("SELECT * FROM tickets WHERE id=? AND status='open'",(tid,)).fetchone()
    if not t:
        st['mode']=None; return
    if msg.text and msg.text in {'❌ انصراف','🚪 خروج از پنل'}:
        st['mode']='partner' if mode=='ticket_partner' else 'admin'
        await msg.reply_text('❌ چت بسته شد.', reply_markup=_partner_kb() if mode=='ticket_partner' else B.amenu())
        raise ApplicationHandlerStop
    role='partner' if mode=='ticket_partner' else 'admin'
    sender=str(uid)
    if role=='partner':
        recipients=[int(x) for x in B.ADM if str(x).isdigit()]
        if not recipients: return
        p=B.db.conn.execute('SELECT name,phone FROM partners WHERE id=?',(t['partner_id'],)).fetchone()
        header=f"🎫 پیام همکار\n👤 {p['name'] if p else '-'}\n📱 {p['phone'] if p else '-'}\n🎫 تیکت #{tid}"
        for aid in recipients:
            try:
                await context.bot.send_message(aid,header,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('↩️ پاسخ مجدد',callback_data=f'tk:reply:{tid}')]]))
                await msg.copy(chat_id=aid, reply_markup=_admin_reply_kb())
            except Exception: log.exception('ticket partner->admin')
    else:
        pid=int(t['partner_id']); link=B.db.conn.execute('SELECT telegram_user_id FROM partner_telegram_links WHERE partner_id=?',(pid,)).fetchone()
        if not link: return await msg.reply_text('❌ حساب تلگرام همکار پیدا نشد.')
        target=int(link['telegram_user_id'])
        await msg.copy(chat_id=target, reply_markup=_partner_reply_kb(tid))
    kind='text' if msg.text else 'photo' if msg.photo else 'video' if msg.video else 'voice' if msg.voice else 'document' if msg.document else 'other'
    fid=(msg.photo[-1].file_id if msg.photo else msg.video.file_id if msg.video else msg.voice.file_id if msg.voice else msg.document.file_id if msg.document else '')
    B.db.conn.execute('INSERT INTO ticket_messages(ticket_id,sender_role,sender_id,kind,text,file_id,created_at) VALUES(?,?,?,?,?,?,?)',(tid,role,sender,kind,msg.text or msg.caption or '',fid,_now()))
    B.db.conn.execute('UPDATE tickets SET updated_at=? WHERE id=?',(_now(),tid));B.db.conn.commit()
    raise ApplicationHandlerStop


def install(app,B):
    if getattr(B,'_telegram_business_features',False): return
    _ensure(B)
    B.kb=_persistent_kb
    B.partner_kb=lambda lang='fa': _partner_kb()
    # Link partner as soon as the existing partner login succeeds, without replacing login logic.
    original_partner=B.partner
    async def partner(update,context):
        result=await original_partner(update,context)
        uid=update.effective_user.id; pid=B.S.get(uid,{}).get('partner_id')
        if pid: _link(B,pid,uid)
        return result
    B.partner=partner
    # Ticket button is handled before the generic router.
    async def ticket_text(update,context):
        if not update.message: return
        uid=update.effective_user.id; t=(update.message.text or '').strip()
        if t=='🎫 تیکت به مدیریت':
            await _send_ticket_prompt(update,B); raise ApplicationHandlerStop
        if B.admin(uid) and t in {'✉️ پیام به همکاران','🎫 پیام به همکار'}:
            B.S.setdefault(uid,{})['mode']='ticket_admin_choose'; await update.message.reply_text('🎫 برای انتخاب همکار از دکمه زیر استفاده کنید.',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('👥 انتخاب همکار',callback_data='tk:partners')]])); raise ApplicationHandlerStop
        if B.admin(uid) and B.S.get(uid,{}).get('mode')=='ticket_admin_choose':
            raise ApplicationHandlerStop
    app.add_handler(CallbackQueryHandler(lambda u,c:_callback(u,c,B), pattern=r'^tk:'), group=-30)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ticket_text), group=-30)
    app.add_handler(MessageHandler((filters.TEXT & ~filters.COMMAND)|filters.PHOTO|filters.VIDEO|filters.VOICE|filters.Document.ALL, lambda u,c:_forward(u,c,B)), group=-25)
    B._telegram_business_features=True
    log.info('Telegram business features installed')
