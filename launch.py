"""Start the Mac mini loopback service. External publishing is disabled."""
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
def read(name,default):
    try:return json.loads((DATA/name).read_text())
    except (OSError,ValueError):return default

def main():
    if read('authority.json',{}).get('server_url'):
        print('Mac miniの管理画面へ接続します。終了するまでこのウインドウを開いておいてください。',flush=True)
        return subprocess.call(['ssh','-NT','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=30','-L','127.0.0.1:18765:127.0.0.1:18765','mac-mini'])
    DATA.mkdir(parents=True,exist_ok=True)
    try:
        with urllib.request.urlopen('http://127.0.0.1:18765/api/health',timeout=2) as response:up=json.load(response).get('ok')
    except Exception:up=False
    if not up:
        with (DATA/'app.log').open('a') as log:
            process=subprocess.Popen([sys.executable,str(ROOT/'app.py'),'--port','18765'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        (DATA/'app.pid').write_text(str(process.pid))
    print(json.dumps({'local_url':'http://127.0.0.1:18765/','host':'Mac mini','external_access':False},ensure_ascii=False))
if __name__=='__main__':sys.exit(main() or 0)
