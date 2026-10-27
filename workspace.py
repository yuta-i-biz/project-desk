"""Copy an explicitly registered repository into a request; never mutate its Git tree."""
import argparse,difflib,hashlib,json,os,re,shutil,sqlite3,subprocess,tempfile
from pathlib import Path
MAX_FILES=5000
MAX_BYTES=100*1024*1024
MAX_FILE=5*1024*1024
EXCLUDED={'.git','.svn','.hg','node_modules','venv','.venv','__pycache__','data','uploads','vendor','dist','build','.next','.cache','.ssh','.aws','.codex'}
SECRET_NAMES={'credentials.json','secrets.json','token.json','tokens.json','settings.local.json','access.json','.mcp.json','.npmrc','.pypirc','.netrc','id_rsa','id_ed25519','id_ecdsa','auth.json','.claude.json'}
def excluded(name):
 p=Path(name)
 return any(part.lower() in EXCLUDED for part in p.parts) or p.name.lower() in SECRET_NAMES or re.search(r'(^|[_.-])(credentials?|secrets?|tokens?)([_.-]|$)',p.name.lower()) is not None or p.name.lower().startswith('.env') or p.suffix.lower() in {'.pem','.key','.p12','.pfx','.keychain-db','.sqlite','.sqlite3','.db'}
def git(source,*args):
 return subprocess.run(['git','-c','core.fsmonitor=false','-c','core.hooksPath=/dev/null','-C',str(source),*args],capture_output=True,check=True,timeout=20,env={**os.environ,'GIT_OPTIONAL_LOCKS':'0'}).stdout

def validate(source,home):
 source=Path(source).expanduser().resolve();home=Path(home).resolve()
 if any(source.is_relative_to(home/name) for name in ('.ssh','.aws','.claude','.codex','Library')):raise ValueError('認証情報・アプリ設定のフォルダは登録できません。')
 if not source.is_dir() or not source.is_relative_to(home) or source in (home,home/'Documents',home/'Desktop',home/'Downloads',home/'Documents/Codex'):
  raise ValueError('案件専用のGitリポジトリを登録してください。')
 try:top=Path(os.fsdecode(git(source,'rev-parse','--show-toplevel')).strip()).resolve()
 except (OSError,subprocess.SubprocessError):raise ValueError('登録先のGitリポジトリを確認できません。')
 if top!=source:raise ValueError('リポジトリの一番上のフォルダを登録してください。')
 return source

def register(data,pid,source,home):
 data=Path(data);source=validate(source,home)
 with sqlite3.connect(data/'desk.sqlite3') as c:
  if not c.execute('SELECT 1 FROM projects WHERE id=?',(pid,)).fetchone():raise ValueError('登録済みの案件を指定してください。')
 path=data/'workspace_sources.json'
 records=json.loads(path.read_text()) if path.exists() else {}
 records[pid]={'source':str(source),'mode':'copy','registered_locally':True}
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(records,ensure_ascii=False,indent=2));os.chmod(temp,0o600);os.replace(temp,path)
 return {'project_id':pid,'mode':'copy','registered':True}

def safe_file(source,name):
 source=Path(source).resolve()
 rel=Path(name)
 if rel.is_absolute() or '..' in rel.parts or excluded(name):return False
 p=source
 for part in rel.parts:
  p=p/part
  if p.is_symlink():return False
 return p.is_file() and p.resolve().is_relative_to(source)

def prepare(desk,pid,folder):
 registry=desk.data/'workspace_sources.json'
 if not registry.exists():return None
 records=json.loads(registry.read_text())
 if not isinstance(records,dict):raise ValueError('案件の作業フォルダ登録を読み取れません。')
 record=records.get(pid)
 if record is None:return None
 if not isinstance(record,dict) or record.get('mode')!='copy' or record.get('registered_locally') is not True or not isinstance(record.get('source'),str):raise ValueError('案件の作業フォルダ登録を確認してください。')
 source=validate(record['source'],desk.home);target=folder/'workspace'
 if target.exists() or target.is_symlink():raise ValueError('作業コピーの保存先が既に存在します。')
 names=[os.fsdecode(s) for s in git(source,'ls-files','-z','--cached','--others','--exclude-standard').split(b'\0') if s]
 names=sorted(set(names))
 if len(names)>MAX_FILES:raise ValueError('リポジトリのファイル数が上限を超えています。対象の分割が必要です。')
 selected=[];skipped=[];total=0
 for name in names:
  if not safe_file(source,name):skipped.append(name);continue
  size=(source/name).stat().st_size
  if size>MAX_FILE:raise ValueError('作業コピーの単一ファイルの大きさが上限を超えています。')
  total+=size
  if total>MAX_BYTES:raise ValueError('作業コピーの全体サイズが上限を超えています。')
  selected.append(name)
 target.mkdir(mode=0o700);hashes={}
 try:
  for name in selected:
   if not safe_file(source,name):raise ValueError('複製中に元ファイルが変化しました。')
   before=(source/name).read_bytes();dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(before);shutil.copymode(source/name,dest)
   if not safe_file(source,name) or hashlib.sha256((source/name).read_bytes()).digest()!=hashlib.sha256(before).digest():raise ValueError('複製中に元ファイルが変化しました。')
   hashes[name]=hashlib.sha256(before).hexdigest()
 except Exception:
  shutil.rmtree(target);raise
 manifest={'source':str(source),'mode':'copy','files':hashes,'skipped':skipped,'bytes':total}
 (folder/'workspace_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 return manifest

def public(manifest):
 return {'mode':'copy','path':'workspace','copied_files':len(manifest['files']),'excluded_files':len(manifest['skipped']),'bytes':manifest['bytes'],'original_changes_allowed':False,'dependencies':'除外された依存キャッシュや秘密設定は引き継いでいません。'}

def report(manifest,folder):
 source=Path(manifest['source']);copy=folder/'workspace';unchanged=True;patch=[];changed=[];binary=[]
 if copy.is_symlink() or copy.resolve().parent!=folder.resolve():raise ValueError('作業コピーの保存先が変化しています。')
 for name,digest in manifest['files'].items():
  if not safe_file(source,name) or hashlib.sha256((source/name).read_bytes()).hexdigest()!=digest:unchanged=False;break
 if not unchanged:return {'original_unchanged':False,'summary':'複製対象の元ファイルに変化があり、原本無変更の検証と差分作成を確定できません。'}
 files=set(manifest['files']);scanned=0
 for parent,dirs,names in os.walk(copy,followlinks=False):
  parent=Path(parent)
  for d in dirs:
   if (parent/d).is_symlink() and not excluded(str((parent/d).relative_to(copy))):raise ValueError('作業コピーにシンボリックリンクがあります。')
  dirs[:]=[d for d in dirs if not excluded(str((parent/d).relative_to(copy))) and not (parent/d).is_symlink()]
  for name in names:
   p=parent/name;rel=str(p.relative_to(copy))
   if excluded(rel):continue
   if p.is_symlink():raise ValueError('作業コピーにシンボリックリンクがあります。')
   if safe_file(copy,rel):files.add(rel)
   scanned+=1
   if scanned>MAX_FILES:raise ValueError('作業コピーの検証対象が上限を超えています。')
 if len(files)>MAX_FILES:raise ValueError('作業コピーの検証対象が上限を超えています。')
 patch_size=0
 for name in sorted(files):
  if excluded(name):continue
  old=(source/name).read_bytes() if name in manifest['files'] else b''
  p=copy/name
  if p.exists() and not safe_file(copy,name):raise ValueError('変更後ファイルが作業コピーの外を参照しています。')
  if p.is_symlink():raise ValueError('変更後ファイルがシンボリックリンクです。')
  if p.is_file() and p.stat().st_size>MAX_FILE:raise ValueError('変更後ファイルが大きすぎるため差分検証は未完了です。')
  new=p.read_bytes() if p.is_file() else b''
  if old==new and (name in manifest['files'])==p.is_file():continue
  changed.append(name)
  try:
   if b'\0' in old+new:raise UnicodeError()
   lines=list(difflib.unified_diff(old.decode('utf-8').splitlines(True),new.decode('utf-8').splitlines(True),fromfile='a/'+name if name in manifest['files'] else '/dev/null',tofile='b/'+name if p.is_file() else '/dev/null'))
   # Keep a valid diff when either file lacks its final newline.
   for line in lines:
    if not line.endswith('\n'):line+='\n\\ No newline at end of file\n'
    patch.append(line);patch_size+=len(line.encode('utf-8'))
   if patch_size>MAX_BYTES:raise ValueError('変更差分が大きすぎます。')
  except UnicodeError:binary.append(name)
 if patch:
  fd,temp=tempfile.mkstemp(prefix='.workspace-patch-',dir=folder)
  with os.fdopen(fd,'w') as f:f.write(''.join(patch))
  os.replace(temp,folder/'workspace_changes.patch')
 return {'original_unchanged':True,'changed_files':changed,'binary_changes':binary,'summary':'複製対象の元ファイルは無変更。作業コピー内の変更 '+str(len(changed))+'件。','patch':'workspace_changes.patch' if patch else None}

def main():
 parser=argparse.ArgumentParser(description='案件の作業コピー元をMac mini上で登録します。原本は変更しません。')
 parser.add_argument('--data',type=Path,required=True);parser.add_argument('--project-id',required=True);parser.add_argument('--source',type=Path,required=True)
 a=parser.parse_args();print(json.dumps(register(a.data,a.project_id,a.source,Path.home()),ensure_ascii=False))
if __name__=='__main__':main()

def record_manifest(desk,pid,folder,manifest):
 # The model can edit files in its request, so authoritative provenance is stored outside it.
 with desk.connect() as c:
  task=c.execute('SELECT project_id FROM tasks WHERE id=?',(folder.name,)).fetchone()
  if not task or task[0]!=pid or folder.resolve().parent!=(desk.data/'requests').resolve():raise ValueError('invalid request provenance')
  c.execute('CREATE TABLE IF NOT EXISTS workspace_manifests(task_id TEXT PRIMARY KEY,project_id TEXT NOT NULL,manifest TEXT NOT NULL)')
  c.execute('INSERT INTO workspace_manifests VALUES(?,?,?)',(folder.name,pid,json.dumps(manifest)))


def prepare_previous(desk,pid,folder,parent_id):
 """Carry a prior self-improvement copy forward, retaining original-source hashes."""
 if not isinstance(parent_id,str) or not re.fullmatch(r'task-[a-f0-9]{16}',parent_id):raise ValueError('invalid parent request')
 with desk.connect() as c:
  row=c.execute('SELECT project_id FROM tasks WHERE id=?',(parent_id,)).fetchone()
  owned=c.execute("SELECT state FROM self_growth_runs WHERE task_id=?",(parent_id,)).fetchone()
 if not row or row[0]!=pid or not owned or owned[0]!='superseded':raise ValueError('prior request is outside this improvement project')
 parent=desk.data/'requests'/parent_id
 if parent.is_symlink() or not parent.is_dir() or parent.resolve().parent!=(desk.data/'requests').resolve():raise ValueError('invalid prior request folder')
 receipt_path=parent/'receipt.json'
 if receipt_path.is_symlink() or receipt_path.stat().st_size>2*1024*1024:raise ValueError('invalid prior metadata')
 with desk.connect() as c:
  stored=c.execute('SELECT manifest FROM workspace_manifests WHERE task_id=? AND project_id=?',(parent_id,pid)).fetchone()
 if not stored:raise ValueError('trusted prior manifest missing')
 manifest=json.loads(stored[0]);receipt=json.loads(receipt_path.read_text())
 if receipt.get('execution_status')!='succeeded' or (receipt.get('review') or {}).get('status') not in ('reviewed','issues') or (receipt.get('workspace') or {}).get('original_unchanged') is not True:raise ValueError('prior execution is not verified')
 source=validate(manifest['source'],desk.home)
 if report(manifest,parent).get('original_unchanged') is not True:raise ValueError('original source changed')
 previous=parent/'workspace';prior=report(manifest,parent)
 # Start from the latest registered baseline; only carry edits whose original
 # content has not changed. A conflicting baseline is held, never overwritten.
 baseline=prepare(desk,pid,folder)
 if baseline is None:raise ValueError('registered baseline missing')
 target=folder/'workspace'
 try:
  total=0
  for name in prior.get('changed_files',[]):
   if excluded(name) or Path(name).is_absolute() or '..' in Path(name).parts:raise ValueError('unsafe prior change')
   if manifest['files'].get(name)!=baseline['files'].get(name):raise ValueError('new baseline conflicts with prior change')
   src=previous/name;dest=target/name
   if src.is_symlink():raise ValueError('unsafe prior file')
   if src.is_file():
    if not safe_file(previous,name):raise ValueError('unsafe prior file')
    before=src.read_bytes();total+=len(before)
    if len(before)>MAX_FILE or total>MAX_BYTES:raise ValueError('prior changes too large')
    if not safe_file(previous,name):raise ValueError('prior file changed')
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(before);shutil.copymode(src,dest)
    if not safe_file(previous,name) or hashlib.sha256(src.read_bytes()).digest()!=hashlib.sha256(before).digest():raise ValueError('prior file changed during copy')
   elif dest.is_file():dest.unlink()
 except Exception:
  shutil.rmtree(target);(folder/'workspace_manifest.json').unlink(missing_ok=True);raise
 return baseline
