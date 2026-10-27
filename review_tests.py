"""Host-owned test evidence from a disposable, filesystem-restricted copy."""
import hashlib,json,os,re,shutil,subprocess,sys,tempfile
from pathlib import Path

def run(workspace):
 workspace=Path(workspace)
 if not workspace.is_dir() or workspace.is_symlink():return {'status':'unverified','reason':'登録コードのコピーがありません。'}
 sandbox=Path('/usr/bin/sandbox-exec')
 if not sandbox.is_file():return {'status':'unverified','reason':'隔離テスト機能がありません。'}
 with tempfile.TemporaryDirectory(prefix='project-desk-test-') as tmp:
  root=Path(tmp).resolve();copy=root/'workspace'
  # Never follow model-created links into originals or credentials.
  files=[p for p in workspace.rglob('*') if p.is_file()]
  if any(p.is_symlink() for p in workspace.rglob('*')):return {'status':'unverified','reason':'作業コピーにリンクが含まれます。'}
  if len(files)>5000 or sum(p.stat().st_size for p in files)>100_000_000:return {'status':'unverified','reason':'作業コピーが検証上限を超えています。'}
  shutil.copytree(workspace,copy)
  manifest={str(p.relative_to(workspace)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
  profile='(version 1)(allow default)(deny file-read* (subpath "/Users") (subpath "/Volumes"))(deny file-write*)(allow file-write* (subpath '+json.dumps(str(root))+') (literal "/dev/null"))(deny network*)(allow network-bind (local ip "localhost:*"))(allow network-inbound (local ip "localhost:*"))(allow network-outbound (remote ip "localhost:*"))'
  # No credentials or provider environment is inherited by test code.
  env={'PATH':'/usr/bin:/bin:/opt/homebrew/bin','HOME':str(root),'TMPDIR':str(root),'PYTHONDONTWRITEBYTECODE':'1','LC_ALL':'en_US.UTF-8'}
  try:
   result=subprocess.run([str(sandbox),'-p',profile,sys.executable,'-m','unittest','discover'],cwd=copy,env=env,capture_output=True,text=True,timeout=180)
   output=result.stdout+result.stderr;count=re.search(r'Ran\s+(\d+)\s+tests?',output)
   passed=result.returncode==0 and count and int(count.group(1))>0
   return {'status':'passed' if passed else 'unverified','exit_code':result.returncode,'test_count':int(count.group(1)) if count else 0,'output':output[-20000:],'manifest':manifest,'runner':'unittest','source':'host-owned isolated test process','network':'loopback only','writes':'disposable copy only'}
  except (OSError,subprocess.TimeoutExpired) as e:return {'status':'unverified','reason':type(e).__name__}
