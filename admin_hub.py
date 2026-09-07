import os,re,requests
from core import db
PLATFORMS={'telegram':'تلگرام','rubika':'روبیکا','eitaa':'ایتا','bale':'بله'}
def menu(): return [[('a_partners','👥 مدیریت همکاران'),('a_bots','🤖 مدیریت بات‌ها')],[('a_addbot','➕ افزودن بات'),('a_notify','🔔 اعلان‌ها')],[('a_reports','📊 گزارش کامل'),('a_prices','💰 مدیریت قیمت‌ها')],[('a_exit','🚪 خروج')]]
def render():
 rows=db.bots(); text='🤖 بات‌های متصل\n'
 if not rows: text+='هنوز بات دیگری ثبت نشده است.\n'
 for r in rows: text+=f"#{r['id']} | {r['platform']} | {r['bot_name']} | {'🟢' if r['active'] else '🔴'} {r['status']}\n"
 return text
def validate_platform_token(platform,token):
 token=token.strip()
 if platform=='bale':
  j=requests.get(f'https://tapi.bale.ai/bot{token}/getMe',timeout=15).json(); return bool(j.get('ok')),j
 if platform=='telegram':
  j=requests.get(f'https://api.telegram.org/bot{token}/getMe',timeout=15).json(); return bool(j.get('ok')),j
 if platform=='eitaa':
  j=requests.post(f'https://eitaayar.ir/api/{token}/getMe',timeout=15).json(); return bool(j.get('ok',j.get('status') in ('OK',200))),j
 if platform=='rubika':
  j=requests.post(f'https://botapi.rubika.ir/v3/{token}/getMe',json={},timeout=15).json(); return j.get('status')=='OK',j
 return False,{'description':'platform not supported'}
def add_bot(platform,name,token):
 ok,_=validate_platform_token(platform,token)
 ref=f'{platform.upper()}_BOT_TOKEN_{re.sub(r"[^A-Za-z0-9]","_",name.upper())}'
 db.add_bot(platform,name,ref); db.audit('system','admin','add_bot',platform,f'name={name};validated={ok};secret_ref={ref}')
 return ok,ref
