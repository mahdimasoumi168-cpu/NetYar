import re
with open('server.py', 'r') as f:
    content = f.read()

old = 'asyncio.create_task(asyncio.to_thread(rb.send,chat,rb.TEXT["fa"]["lang"],[[\"1\",\"🇮🇷 فارسی\"],[\"2\",\"🇬🇧 English\"],[\"3\",\"🇸🇦 العربية\"]]])'
new = 'asyncio.create_task(asyncio.to_thread(rb.send,chat,rb.T(uid,"lang"),[[("1","🇮🇷 فارسی"),("2","🇬🇧 English"),("3","🇸🇦 العربية")]]))'

content = content.replace(old, new)
with open('server.py', 'w') as f:
    f.write(content)
print("Fixed Rubika StartedBot handler")
