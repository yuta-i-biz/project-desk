"""MacBook sender. Existing SSH alias only; no API/AI calls or originals changed."""
import argparse,datetime,hashlib,json,os,shlex,subprocess
from pathlib import Path
from remote_export import export
from peer_receiver import fingerprint,atomic

def sync(state,home=None,runner=subprocess.run,automatic=False):
 state=Path(state);state.mkdir(parents=True,exist_ok=True)
 stamp=datetime.datetime.now(datetime.timezone.utc).isoformat();previous={}
 try:previous=json.loads((state/'sync_status.json').read_text())
 except (OSError,ValueError):pass
 try:
  try:cache=json.loads((state/'session_cache.json').read_text())
  except (OSError,ValueError):cache={}
  if not isinstance(cache,dict):cache={}
  snapshot=export(home=home,machine='MacBook',include_documents=True,session_cache=cache)
  atomic(state/'session_cache.json',cache)
  if snapshot['errors']:raise ValueError('incomplete source')
  digest=fingerprint(snapshot);changed=digest!=previous.get('fingerprint')
  envelope={'machine':'MacBook','automatic':automatic,'captured_at':stamp,'fingerprint':digest,'snapshot':snapshot if changed else None}
  command=['/usr/bin/ssh','-T','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes','mac-mini','/usr/bin/python3 -c '+shlex.quote(Path(__file__).with_name('peer_receiver.py').read_text())]
  for attempt in range(2):
   result=runner(command,input=json.dumps(envelope,ensure_ascii=False),text=True,capture_output=True,timeout=45)
   if result.returncode:raise RuntimeError('ssh failure')
   response=json.loads(result.stdout)
   if response.get('needs_full') and attempt==0:envelope['snapshot']=snapshot;changed=True;continue
   if response.get('ok') is not True or response.get('fingerprint')!=digest:raise ValueError('unacknowledged snapshot')
   break
  status={'ok':True,'last_success':stamp,'attempted_at':stamp,'fingerprint':digest,'changed':changed,'sources':len(snapshot['sources']),'claude_sessions':len(snapshot['sessions']),'coverage':snapshot['coverage']}
 except (OSError,ValueError,TypeError,KeyError,RuntimeError,subprocess.TimeoutExpired):status={'ok':False,'attempted_at':stamp,'last_success':previous.get('last_success'),'error':'Mac miniへの読取記録の転送が未完了。最後の取得記録を保持しています。'}
 atomic(state/'sync_status.json',status)
 return status

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--state',type=Path,required=True);p.add_argument('--home',type=Path);p.add_argument('--automatic',action='store_true');a=p.parse_args();r=sync(a.state,a.home,automatic=a.automatic)
 if not r['ok'] or r.get('changed'):print(json.dumps(r,ensure_ascii=False))
 raise SystemExit(0 if r['ok'] else 1)
