# NetYar Safe Repair Plan — 2026-09-14

This branch is a safety checkpoint before consolidating the runtime.

Goals:
- preserve existing service flows and data structures;
- eliminate conflicting Telegram handler ownership;
- keep one canonical Telegram webhook runtime;
- keep platform adapters isolated;
- prevent duplicate callback/message processing;
- preserve admin, partner, government, billing and document flows;
- verify Rubika/Eitaa/Bale independently rather than allowing one platform failure to break Telegram.

No destructive migration is performed in this checkpoint.
