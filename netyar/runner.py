import os
import signal
import subprocess
import sys
import time

procs = []


def stop_all(*_):
    for p in procs:
        if p.poll() is None:
            p.terminate()
    deadline = time.time() + 10
    for p in procs:
        while p.poll() is None and time.time() < deadline:
            time.sleep(0.2)
    for p in procs:
        if p.poll() is None:
            p.kill()
    raise SystemExit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop_all)
    signal.signal(signal.SIGINT, stop_all)
    env = os.environ.copy()
    procs = [
        subprocess.Popen([sys.executable, "bot.py"], env=env),
        subprocess.Popen([sys.executable, "rubika_bot.py"], env=env),
    ]
    print("NetYar: Telegram + Rubika workers started", flush=True)
    try:
        while True:
            for p in procs:
                if p.poll() is not None:
                    raise SystemExit(p.returncode or 1)
            time.sleep(2)
    finally:
        stop_all()
