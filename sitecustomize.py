"""NetYar startup hook intentionally kept empty.

Runtime behavior is explicit in entrypoint.py -> server.py. This file must not
patch asyncio, Telegram handlers, routers, or application state implicitly.
"""
