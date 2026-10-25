"""Explicitly enable an authenticated, temporary HTTPS preview on Mac mini."""
import argparse,json,os,re,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
def save(name,value):
    p=DATA/name;tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False));tmp.chmod(0o600);tmp.replace(p)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--enable',action='store_true');args=parser.parse_args()
    if not args.enable:
        print('外出先接続は無効です。明示的な許可後に --enable を指定してください。');return
    node=json.loads((DATA/'node.json').read_text())
    if node.get('name')!='Mac mini':raise RuntimeError('Mac miniで実行してください。')
    logpath=DATA/'remote-access.log'
    with logpath.open('w') as log:
        process=subprocess.Popen(['/opt/homebrew/bin/cloudflared','tunnel','--url','http://127.0.0.1:18767','--no-autoupdate','--protocol','http2'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    save('remote-access-process.json',{'pid':process.pid})
    for _ in range(45):
        if process.poll() is not None:raise RuntimeError('接続プロセスが終了しました。ログの確認が必要です。')
        match=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',logpath.read_text(errors='replace'))
        if match:
            url=match.group(0);save('network.json',{'origin':url,'origins':['http://127.0.0.1:18767'],'external_access':True})
            save('public_url.json',{'url':url,'temporary_preview':True,'host':'Mac mini','authentication_required':True})
            print(json.dumps({'url':url,'temporary_preview':True,'authentication_required':True,'host':'Mac mini'},ensure_ascii=False));return
        time.sleep(1)
    process.terminate();raise RuntimeError('一時URLを取得できませんでした。')
if __name__=='__main__':main()
