"""NetYar single production entrypoint."""
import os
import logging
import uvicorn
import server

log = logging.getLogger("netyar.entrypoint")
BUILD = "2026-09-19-single-server-owner-v1"

def main() -> None:
    port = int(os.getenv("PORT", "8080"))
    log.info("NetYar build=%s; lifecycle owner=server.py", BUILD)
    uvicorn.run(server.api, host="0.0.0.0", port=port, lifespan="on")

if __name__ == "__main__":
    main()
