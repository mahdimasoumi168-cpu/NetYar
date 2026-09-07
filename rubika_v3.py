import rubika_v2

def chat_of(u):
    m=u.get('new_message') or u.get('updated_message') or u.get('message') or {}
    return str(u.get('chat_id') or m.get('chat_id') or '')

def user_of(u):
    m=u.get('new_message') or u.get('updated_message') or u.get('message') or {}
    return str(m.get('sender_id') or m.get('user_id') or u.get('user_id') or u.get('chat_id') or m.get('chat_id') or '')

def text_of(u):
    m=u.get('new_message') or u.get('updated_message') or u.get('message') or {}
    text=str(m.get('text') or '').strip()
    if text:return text
    aux=m.get('aux_data') or {}
    if isinstance(aux,dict):return str(aux.get('button_id') or aux.get('button_text') or '').strip()
    return ''

rubika_v2.chat_of=chat_of
rubika_v2.user_of=user_of
rubika_v2.text_of=text_of
rubika_v2.log.info('Rubika v3 routing hotfix loaded')

if __name__=='__main__':
    rubika_v2.main()
