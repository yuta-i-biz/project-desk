"""Expose only the authenticated listener after explicit user authorization."""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'
CLI='/Applications/Tailscale.app/Contents/MacOS/Tailscale'
def save(name,value):
    p=DATA/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(value,ensure_ascii=False));t.chmod(0o600);t.replace(p)
def main():
    p=argparse.ArgumentParser();p.add_argument('--enable',action='store_true');args=p.parse_args()
    if not args.enable:print('明示的な許可後に --enable を指定してください。');return
    node=json.loads((DATA/'node.json').read_text())
    if node.get('name')!='Mac mini':raise RuntimeError('Mac miniで実行してください。')
    status=subprocess.run([CLI,'status','--json'],capture_output=True,text=True,timeout=15,check=True)
    host=json.loads(status.stdout)['Self']['DNSName'].rstrip('.')
    config=subprocess.run([CLI,'funnel','status','--json'],capture_output=True,text=True,timeout=15,check=True)
    old=json.loads(config.stdout or '{}')
    target=old.get('Web',{}).get(host+':443',{}).get('Handlers',{}).get('/',{}).get('Proxy')
    if target and target!='http://127.0.0.1:18767':raise RuntimeError('既存の443番接続があるため停止しました。')
    subprocess.run([CLI,'funnel','--bg','--https=443','http://127.0.0.1:18767'],timeout=45,check=True)
    config=subprocess.run([CLI,'funnel','status','--json'],capture_output=True,text=True,timeout=15,check=True)
    current=json.loads(config.stdout or '{}')
    if not current.get('AllowFunnel',{}).get(host+':443'):raise RuntimeError('Funnelの有効化が未確認です。')
    url='https://'+host
    save('network.json',{'origin':url,'origins':['http://127.0.0.1:18767'],'external_access':True,'provider':'Tailscale Funnel','activation_pending':False})
    save('public_url.json',{'url':url,'provider':'Tailscale Funnel','temporary_preview':False,'host':'Mac mini','authentication_required':True})
    print(json.dumps({'url':url,'provider':'Tailscale Funnel','authentication_required':True},ensure_ascii=False))
if __name__=='__main__':main()
