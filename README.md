# NetYar Admin v3

Railway variables:
- BOT_TOKEN = your bot token
- ADMIN_IDS = numeric Telegram user ID(s), comma-separated

Commands:
- /start
- /admin
- /myid

Important:
1. Do not upload BOT_TOKEN into GitHub.
2. Replace the existing bot.py, requirements.txt and Procfile with these files.
3. Commit to GitHub and let Railway redeploy.
4. In Telegram send /myid first. The bot returns your numeric ID and whether it is currently recognized as an admin.
5. If it says Admin: no, copy that numeric ID into Railway ADMIN_IDS, save, redeploy, then send /admin.
