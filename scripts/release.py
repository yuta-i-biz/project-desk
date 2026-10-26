import argparse,hashlib,io,json,pathlib,shlex,subprocess,tarfile
parser=argparse.ArgumentParser();parser.add_argument("--base",required=True);args=parser.parse_args()
root=pathlib.Path(__file__).resolve().parents[1]
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
files=[name for name in subprocess.check_output(['git','diff','--name-only',args.base,'HEAD'],cwd=root,text=True).splitlines() if not name.startswith(('test','scripts/')) and name not in ('README.rst','CHANGELOG.rst','deploy.sh')]
allowed={}
for name in files:
 hashes=[]
 for ref in [args.base]:
  r=subprocess.run(['git','show',ref+':'+name],cwd=root,capture_output=True)
  if r.returncode==0:hashes.append(hashlib.sha256(r.stdout).hexdigest())
 allowed[name]=hashes
manifest={'revision':revision,'allowed':allowed,'hashes':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}}
buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w:gz') as archive:
 for name in files:archive.add(root/name,arcname=name,recursive=False)
 data=json.dumps(manifest).encode();info=tarfile.TarInfo('release-manifest.json');info.size=len(data);archive.addfile(info,io.BytesIO(data))
remote=r'''import datetime,hashlib,io,json,os,pathlib,re,signal,sqlite3,subprocess,sys,tarfile,tempfile,time,urllib.request,shutil
root=pathlib.Path.home()/'Documents/Codex/project-desk'
stage=pathlib.Path(tempfile.mkdtemp(prefix='.project-desk-release-',dir=root.parent))
archive=tarfile.open(fileobj=io.BytesIO(sys.stdin.buffer.read()),mode='r:gz')
for member in archive.getmembers():
 if member.name.startswith('/') or '..' in pathlib.PurePosixPath(member.name).parts or member.issym() or member.islnk():raise ValueError('Invalid archive')
archive.extractall(stage)
m=json.loads((stage/'release-manifest.json').read_text());digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,expected in m['hashes'].items():
 if digest(stage/name)!=expected:raise RuntimeError('Package hash mismatch: '+name)
 live=root/name
 if live.exists() and digest(live) not in m['allowed'][name]+[expected]:raise RuntimeError('Unexpected live change; preserved: '+name)
r=subprocess.run(['lsof','-tiTCP:18765','-sTCP:LISTEN'],capture_output=True,text=True,check=True)
pid=int(r.stdout.strip());args=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
if str(root/'app.py') not in args:raise RuntimeError('Unexpected listener; preserved')
def children(parent):
 table=subprocess.check_output(['ps','-axo','pid=,ppid='],text=True)
 links=[tuple(map(int,line.split())) for line in table.splitlines()];found={parent}
 for _ in range(12):
  new={p for p,pp in links if pp in found}-found
  if not new:break
  found.update(new)
 return found-{parent}
if children(pid):raise RuntimeError('AI or other child process is active; deployment deferred')
with sqlite3.connect(root/'data/desk.sqlite3') as db:
 for tid,status in db.execute("SELECT id,status FROM tasks WHERE status='作業中'"):
  folder=root/'data/requests'/tid
  if (folder/'project_context.json').exists() and (not (folder/'receipt.json').exists() or ((folder/'cli.log').exists() and (folder/'cli.log').stat().st_mtime>(folder/'receipt.json').stat().st_mtime)):raise RuntimeError('Request may still be active; deployment deferred: '+tid)
stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');backup=root.parent/'project-desk-backups'/stamp;backup.mkdir(parents=True,mode=0o700)
existed=[]
for name in m['hashes']:
 src=root/name
 if src.exists():
  dst=backup/'code'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);existed.append(name)
with sqlite3.connect(root/'data/desk.sqlite3') as src,sqlite3.connect(backup/'desk.sqlite3') as dst:src.backup(dst)
os.chmod(backup/'desk.sqlite3',0o600)
access_hash=digest(root/'data/access.json')
(backup/'manifest.json').write_text(json.dumps({'revision':m['revision'],'existing_files':existed,'files':list(m['hashes'])},indent=2))
os.kill(pid,signal.SIGINT)
for _ in range(100):
 try:os.kill(pid,0)
 except ProcessLookupError:break
 time.sleep(.1)
else:raise RuntimeError('Server did not stop; no code files were changed')
def start():
 with (root/'data/app.log').open('a') as log:
  process=subprocess.Popen([sys.executable,str(root/'app.py'),'--port','18765'],cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 (root/'data/app.pid').write_text(str(process.pid));return process
try:
 for name in m['hashes']:
  target=root/name;target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_name(target.name+'.release-tmp');shutil.copy2(stage/name,temporary);os.replace(temporary,target)
 process=start();healthy=False
 for _ in range(80):
  if process.poll() is not None:break
  try:
   with urllib.request.urlopen('http://127.0.0.1:18765/api/health',timeout=1) as response:healthy=json.load(response).get('ok') is True
   if healthy:break
  except Exception:pass
  time.sleep(.2)
 if not healthy:raise RuntimeError('New version failed health check')
 for name,expected in m['hashes'].items():
  if name.startswith('static/'):
   url='http://127.0.0.1:18765/'+('' if name=='static/index.html' else name.split('/',1)[1])
   with urllib.request.urlopen(url,timeout=5) as response:
    body=response.read()
    if name=='static/index.html':body=re.sub(rb'(<meta name="desk-token" content=")[^"]*(")',rb'\1__CSRF_TOKEN__\2',body)
    if hashlib.sha256(body).hexdigest()!=expected:raise RuntimeError('Served content mismatch: '+name)
 if digest(root/'data/access.json')!=access_hash:raise RuntimeError('Access settings unexpectedly changed')
 for name,expected in m['hashes'].items():
  if digest(root/name)!=expected:raise RuntimeError('Live source mismatch: '+name)
 result={'revision':m['revision'],'backup':str(backup),'files':len(m['hashes']),'health':healthy,'access_preserved':True,'pid':process.pid}
 (root/'data/deployment.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
except Exception:
 if 'process' in locals() and process.poll() is None:
  process.send_signal(signal.SIGINT);process.wait(timeout=10)
 for name in m['hashes']:
  if name in existed:shutil.copy2(backup/'code'/name,root/name)
  elif (root/name).exists():(root/name).unlink()
 start();raise
finally:shutil.rmtree(stage)
'''
r=subprocess.run(['ssh','mac-mini','python3 -c '+shlex.quote(remote)],input=buf.getvalue(),capture_output=True,timeout=45)
# Deployment result contains only revision, backup path and health status.
print(r.stdout.decode(errors='replace'));print(r.stderr.decode(errors='replace')[:1500] if r.returncode else '');raise SystemExit(r.returncode)
