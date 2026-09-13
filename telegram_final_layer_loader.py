"""Synchronous startup loader for final Telegram layers.

entrypoint.py invokes plugin installers synchronously. These final layers are
async installer functions, so schedule them on the already-running event loop.
Their installers register handlers without awaiting network I/O.
"""
import asyncio


def install(app, B):
    async def run():
        import telegram_final_admin_navigation_v3 as N
        import telegram_final_text_editor_v2 as E
        await N.install(app, B)
        await E.install(app, B)
    loop = asyncio.get_running_loop()
    loop.create_task(run())
    return True
