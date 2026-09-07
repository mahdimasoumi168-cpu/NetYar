import os, signal, subprocess, sys, time
children={}; stop_requested=False

def stop_all(*_):
    global stop_requested
    stop_requested=True
    for p in list(children.values()):
        if p.poll() is None:p.terminate()
    deadline=time.time()+10
    while time.time()<deadline and any(p.poll() is None for p in children.values()):time.sleep(.2)
    for p in list(children.values()):
        if p.poll() is None:p.kill()
    raise SystemExit(0)

def spawn(name,script):
    env=os.environ.copy()
    if name=='telegram':env.pop('TELEGRAM_WEBHOOK_URL',None)
    p=subprocess.Popen([sys.executable,script],env=env);children[name]=p
    print(f'NetYar: {name} worker started pid={p.pid}',flush=True)

if __name__=='__main__':
    if os.getenv('DISABLE_BOTS','0')=='1':
        print('NetYar worker mode: bot polling disabled',flush=True)
        while True:time.sleep(3600)
    signal.signal(signal.SIGTERM,stop_all);signal.signal(signal.SIGINT,stop_all)
    spawn('telegram','bot.py');spawn('rubika','rubika_v3.py')
    print('NetYar: Telegram + Rubika v3 polling workers started',flush=True)
    try:
        while not stop_requested:
            for name,script in (('telegram','bot.py'),('rubika','rubika_v3.py')):
                p=children.get(name)
                if p is None or p.poll() is not None:
                    if stop_requested:break
                    code=None if p is None else p.returncode
                    print(f'NetYar: {name} worker stopped ({code}); restarting in 2s',flush=True);time.sleep(2)
                    if not stop_requested:spawn(name,script)
            time.sleep(1)
    finally:stop_all()
