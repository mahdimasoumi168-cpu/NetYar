import rubika_runtime as R

# Rubika's official model puts keypad clicks in Message.aux_data.button_id.
# Keep the existing business logic, but normalize every supported form so language
# buttons never fall back to the language question again.
_original_process = R.process

def _text(msg):
    if not isinstance(msg,dict): return ''
    text=str(msg.get('text') or '').strip()
    if text: return text
    aux=msg.get('aux_data') or {}
    if isinstance(aux,dict):
        for k in ('button_id','button_id_string','button_text','text'):
            v=aux.get(k)
            if v is not None and str(v).strip(): return str(v).strip()
    for k in ('button_id','button_text'):
        v=msg.get(k)
        if v is not None and str(v).strip(): return str(v).strip()
    return ''

def _language_choice(value):
    v=(value or '').strip()
    aliases={
        '1':'fa','2':'en','3':'ar','fa':'fa','en':'en','ar':'ar',
        'فارسی':'fa','🇮🇷 فارسی':'fa','farsi':'fa',
        'English':'en','🇬🇧 English':'en','english':'en',
        'العربية':'ar','🇸🇦 العربية':'ar','arabic':'ar',
    }
    return aliases.get(v) or aliases.get(v.replace('🇮🇷 ','').replace('🇬🇧 ','').replace('🇸🇦 ',''))

def process(update):
    if not isinstance(update,dict): return
    msg=R.msg_payload(update)
    chat=str(update.get('chat_id') or msg.get('chat_id') or '')
    if not chat: return
    uid=chat
    if update.get('type')=='StoppedBot': return
    if update.get('type')=='StartedBot':
        R.S[uid]={'lang':'fa','step':'language'}
        R.send(chat,R.TEXT['fa']['lang'],R.lang_menu())
        return
    t=_text(msg)
    if t.startswith('/start'):
        R.S[uid]={'lang':'fa','step':'language'}
        R.send(chat,R.TEXT['fa']['lang'],R.lang_menu())
        return
    st=R.S.setdefault(uid,{'lang':'fa','step':'language'})
    if st.get('step')=='language':
        lang=_language_choice(t)
        if lang:
            st['lang']=lang; st['step']='citizenship'
            R.send(chat,R.TEXT[lang]['cit'],R.cit_menu(lang))
        else:
            R.send(chat,R.TEXT['fa']['lang'],R.lang_menu())
        return
    # Feed the normalized button/text into the existing complete workflow.
    R.process = _original_process
    try:
        if isinstance(msg,dict) and t and not msg.get('text'):
            # Preserve button selection semantics for the existing router.
            aux=msg.get('aux_data')
            if not isinstance(aux,dict): msg['aux_data']={}
            msg['aux_data']['button_id']=t
        _original_process(update)
    finally:
        R.process = process

R.process=process
R.msg_text=_text
R.run()
