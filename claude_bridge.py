"""Run Claude in the Mac's signed-in desktop session, without exporting credentials.

Activation is explicit. The app can only queue Claude requests in its own existing
request folders; jobs cannot supply a command, binary or arbitrary working path.
"""
import argparse,datetime,json,os,re,shutil,subprocess,time,uuid
from pathlib import Path
TASK=re.compile(r'task-[a-f0-9]{16}')

def atomic(path,value):
 temp=path.with_name(path.name+'.tmp-'+uuid.uuid4().hex);temp.write_text(json.dumps(value,ensure_ascii=False));os.chmod(temp,0o600);os.replace(temp,path)

def bridge_data(data):
 data=Path(data);config=data/'claude_desktop.json'
 if not config.exists():return data
 if config.is_symlink():raise ValueError('Invalid desktop configuration')
 value=json.loads(config.read_text());target=Path(value.get('data',''))
 expected=Path.home()/'Library/Application Support/Project Desk Claude/data'
 if target!=expected or target.is_symlink():raise ValueError('Invalid desktop storage')
 return target

def copy_request(source,target,collect=False):
 # These are disposable execution copies, never the primary task database.
 protected={'AGENTS.md','CLAUDE.md','GEMINI.md','project_context.json','workspace_manifest.json','tool_scope.json','receipt.json'}
 files=[];size=0
 for p in source.rglob('*'):
  if p.is_symlink():raise ValueError('依頼コピーに不正な参照があります。')
  if not p.is_file():continue
  rel=p.relative_to(source)
  if any(x=='__pycache__' or x.startswith('.review') for x in rel.parts):continue
  if collect and len(rel.parts)==1 and p.name in protected:continue
  files.append((p,rel));size+=p.stat().st_size
  if len(files)>6000 or size>150*1024*1024:raise ValueError('依頼コピーの上限を超えています。')
 if collect and (target/'workspace').is_dir():
  # Reflect deletions only inside this disposable execution workspace.
  present={str(rel) for _,rel in files}
  for old in (target/'workspace').rglob('*'):
   if old.is_symlink():raise ValueError('結果の保存先が不正です。')
   if old.is_file() and str(old.relative_to(target)) not in present:old.unlink()
 for p,rel in files:
  dest=target/rel
  if target.is_symlink() or any((target/Path(*rel.parts[:i])).is_symlink() for i in range(1,len(rel.parts)+1)):raise ValueError('結果の保存先が不正です。')
  dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)

def status(data,max_age=90):
 try:
  p=bridge_data(data)/'claude_gui_status.json'
  if p.is_symlink():return None
  s=json.loads(p.read_text())
  if not isinstance(s,dict):return None
  age_limit=max_age if s.get('state')=='connected' else 1300 if s.get('state')=='busy' else 600
  if not 0<=time.time()-s.get('checked_at',0)<=age_limit:return None
  return {'engine':'Claude Code','available':s.get('state')=='connected','state':s.get('state'),'detail':s.get('detail','GUI側の接続を確認しています。'),'bridge':'desktop_session'}
 except (OSError,ValueError,TypeError):return None

def folder_for(data,tid):
 if not isinstance(tid,str) or not TASK.fullmatch(tid):raise ValueError('Invalid task')
 parent=Path(data)/'requests';p=parent/tid
 if parent.is_symlink() or p.is_symlink() or not p.is_dir() or p.resolve().parent!=parent.resolve():raise ValueError('Invalid request folder')
 return p

def request(data,tid,prompt,timeout=1200):
 data=Path(data);original=folder_for(data,tid)
 live=status(data)
 if not live or not live['available']:raise RuntimeError('Claudeの画面側実行プロセスが未接続です。再ログインの前に起動状態を確認してください。')
 service=bridge_data(data)
 mirror=service!=data
 remote_folder=service/'requests'/tid
 if mirror:
  remote_folder.mkdir(parents=True,mode=0o700,exist_ok=False);copy_request(original,remote_folder)
 q=service/'claude_jobs';q.mkdir(mode=0o700,exist_ok=True)
 if q.is_symlink():raise ValueError('Invalid queue')
 job=q/(tid+'.json')
 if job.exists():raise ValueError('同じ依頼の実行はすでに受け付けています。再実行せず結果を確認してください。')
 fd=os.open(job,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:json.dump({'task_id':tid,'created':time.time(),'state':'queued','prompt':prompt},f,ensure_ascii=False)
 until=time.monotonic()+timeout
 while time.monotonic()<until:
  s=json.loads(job.read_text())
  if s.get('state')=='done':
   if mirror:
    copy_request(remote_folder,original,collect=True);shutil.rmtree(remote_folder)
   return subprocess.CompletedProcess(['claude-desktop-bridge'],s.get('returncode',1))
  if s.get('state') in ('interrupted','failed'):
   if mirror and remote_folder.exists():copy_request(remote_folder,original,collect=True);shutil.rmtree(remote_folder)
   raise RuntimeError('Claudeの画面側実行が停止しました。途中の結果を確認してください。')
  time.sleep(.5)
 raise RuntimeError('Claudeの画面側実行が時間切れです。自動再実行はしていません。')

def process_job(data,job,runner=subprocess.run):
 if job.is_symlink():raise ValueError('Invalid queue entry')
 s=json.loads(job.read_text())
 if s.get('state')!='queued':return
 if not 0<=time.time()-s.get('created',0)<=1800:s.update(state='failed',reason='expired');atomic(job,s);return
 folder=folder_for(data,s.get('task_id'));prompt=s.get('prompt')
 if not isinstance(prompt,str) or len(prompt)>1000000:raise ValueError('Invalid prompt')
 s['state']='running';atomic(job,s)
 from execution import environment
 home=Path.home();command=[str(home/'.local/bin/claude'),'-p','--output-format','json','--tools','Read,Glob,Grep,Write,Edit']
 try:
  if (folder/'cli.log').is_symlink():raise ValueError('Invalid log')
  with (folder/'cli.log').open('w') as log:r=runner(command,input=prompt,text=True,stdout=log,stderr=subprocess.STDOUT,cwd=folder,env=environment(home),timeout=1200)
  s.update(state='done',returncode=r.returncode)
 except Exception:s.update(state='failed',reason='execution_failed')
 # Never retain the instruction in the queue once execution ends.
 s.pop('prompt',None);atomic(job,s)

def worker(root):
 data=Path(root)/'data';q=data/'claude_jobs';q.mkdir(mode=0o700,exist_ok=True)
 import fcntl
 lock=(data/'claude_gui.lock').open('a')
 try:fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise RuntimeError('Claudeの画面側実行プロセスは起動済みです。')
 if q.is_symlink():raise ValueError('Invalid queue')
 # A previous process may have stopped mid-command; never rerun it on startup.
 for job in q.glob('task-*.json'):
  try:
   s=json.loads(job.read_text())
   if s.get('state')=='running':s.update(state='interrupted');s.pop('prompt',None);atomic(job,s)
  except (OSError,ValueError):continue
 last=0;interval=30
 from auth_status import claude_probe
 while True:
  if time.monotonic()-last>interval or not last:
   result=claude_probe(Path.home());atomic(data/'claude_gui_status.json',{'checked_at':time.time(),'state':result['state'],'detail':result['detail']});last=time.monotonic();interval=30 if result['available'] else 300
  connected=status(data)
  if connected and connected['available']:
   for job in sorted(q.glob('task-*.json')):
    try:
     if json.loads(job.read_text()).get('state')!='queued':continue
     atomic(data/'claude_gui_status.json',{'checked_at':time.time(),'state':'busy','detail':'Claudeが画面側で別の依頼を実行中です。再ログインは不要です。'})
     process_job(data,job);last=0;break
    except (OSError,ValueError):continue
  time.sleep(1)

def main():
 p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent);a=p.parse_args()
 if not a.worker:raise SystemExit('Mac miniの画面側から --worker で起動してください。')
 worker(a.root)
if __name__=='__main__':main()
