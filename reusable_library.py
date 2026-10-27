"""Project-scoped, content-addressed reusable skills, components and programs."""
import hashlib,json,re,shutil,datetime
from pathlib import Path
KINDS={'skill','component','program'}
ROOT=Path(__file__).resolve().parent

def init(desk):
 with desk.connect() as c:c.execute('CREATE TABLE IF NOT EXISTS reusable_assets(project_id TEXT,name TEXT,digest TEXT,kind TEXT,description TEXT,tags TEXT,folder TEXT,state TEXT,source_task TEXT,created TEXT,offered INTEGER DEFAULT 0,PRIMARY KEY(project_id,name,digest))')

def manifest(folder):
 path=folder/'manifest.json'
 if path.is_symlink() or not path.is_file() or path.stat().st_size>32000:raise ValueError('invalid manifest')
 value=json.loads(path.read_text());name=value['name']
 if not isinstance(name,str) or not re.fullmatch('[a-z0-9][a-z0-9-]{0,63}',name) or value['kind'] not in KINDS:raise ValueError('invalid asset')
 if not isinstance(value['description'],str) or not value['description'].strip() or len(value['description'])>2000:raise ValueError('description required')
 if not isinstance(value.get('tags'),list) or not all(isinstance(t,str) and 1<=len(t)<=100 for t in value['tags']):raise ValueError('invalid tags')
 names=value['files']
 if not isinstance(names,list) or not names or len(set(names))!=len(names):raise ValueError('files required')
 if value['kind']=='skill' and 'SKILL.md' not in names:raise ValueError('skill instructions required')
 if value['kind'] in ('component','program') and not any(isinstance(n,str) and Path(n).suffix in ('.py','.js','.cjs','.mjs','.sh','.sql','.html','.css') for n in names):raise ValueError('reusable implementation required')
 hashes={}
 from project_context import local_file,redact
 for name in ['manifest.json']+names:
  if not isinstance(name,str) or not local_file(folder/name,folder):raise ValueError('out of scope asset')
  data=(folder/name).read_bytes()
  if len(data)>5_000_000:raise ValueError('asset file too large')
  if (folder/name).suffix in ('.md','.json','.py','.js','.txt') and redact(data.decode(errors='replace'))!=data.decode(errors='replace'):raise ValueError('secret-like content in asset')
  hashes[name]=hashlib.sha256(data).hexdigest()
 digest=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
 return value,hashes,digest

def capture(desk,pid,tid,receipt):
 # Called by the host after execution/review. Never accept model-supplied status.
 init(desk);request=desk.data/'requests'/tid
 if request.is_symlink() or not re.fullmatch('task-[a-f0-9]{16}',tid):return []
 with desk.connect() as c:owner=c.execute('SELECT project_id FROM tasks WHERE id=?',(tid,)).fetchone()
 if not owner or owner[0]!=pid:return []
 review=receipt.get('review',{});checked={c['file'] for c in review.get('checks',[]) if isinstance(c,dict) and isinstance(c.get('file'),str)}
 verified=receipt.get('execution_status')=='succeeded' and review.get('status')=='reviewed' and review.get('independent') is True
 test=review.get('test_evidence',{});captured=[]
 for relative in ('reusable','workspace/reusable'):
  base=request/relative
  if not base.is_dir() or base.is_symlink():continue
  for package in sorted(base.iterdir()):
   if not package.is_dir() or package.is_symlink():continue
   try:value,hashes,digest=manifest(package)
   except (ValueError,OSError,KeyError,TypeError):continue
   prefix=str(package.relative_to(request))+'/'
   covered=all(prefix+name in checked for name in hashes)
   tested=relative=='workspace/reusable' and test.get('status')=='passed' and all(test.get('manifest',{}).get('reusable/'+package.name+'/'+name)==sha for name,sha in hashes.items())
   ready=verified and covered and (value['kind']=='skill' or tested)
   target=desk.data/'reusable-assets'/hashlib.sha256(pid.encode()).hexdigest()/value['name']/digest
   if any(p.is_symlink() for p in [desk.data/'reusable-assets',target.parent.parent,target.parent,target]):continue
   target.mkdir(parents=True,exist_ok=True)
   for name in hashes:
    dst=target/name;dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.is_symlink():raise ValueError('asset destination linked')
    shutil.copy2(package/name,dst)
   with desk.connect() as c:c.execute("INSERT INTO reusable_assets(project_id,name,digest,kind,description,tags,folder,state,source_task,created) VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(project_id,name,digest) DO UPDATE SET state=CASE WHEN excluded.state='ready' THEN 'ready' ELSE reusable_assets.state END",(pid,value['name'],digest,value['kind'],value['description'],json.dumps(value['tags'],ensure_ascii=False),str(target),'ready' if ready else 'candidate',tid,datetime.datetime.now(datetime.timezone.utc).isoformat()))
   captured.append({'name':value['name'],'state':'ready' if ready else 'candidate','digest':digest})
 return captured

def catalog(desk,pid=None):
 init(desk)
 with desk.connect() as c:
  rows=c.execute('SELECT project_id,name,kind,description,state,source_task,created,offered,digest FROM reusable_assets'+(' WHERE project_id=?' if pid else '')+' ORDER BY created DESC',(pid,) if pid else ()).fetchall()
 return [dict(r) for r in rows]

def materialize(desk,pid,folder,prompt):
 init(desk);assets=[]
 builtin=ROOT/'reusable'
 if builtin.is_dir():
  for package in sorted(builtin.iterdir()):
   if package.is_dir() and not package.is_symlink():
    value,hashes,digest=manifest(package);assets.append((value,hashes,digest,package,True))
 with desk.connect() as c:rows=c.execute("SELECT * FROM reusable_assets WHERE project_id=? AND state='ready' ORDER BY created DESC",(pid,)).fetchall()
 seen=set()
 for row in rows:
  if row['name'] in seen:continue
  seen.add(row['name']);package=Path(row['folder'])
  from project_context import local_file
  if not local_file(package/'manifest.json',desk.data/'reusable-assets'):continue
  try:value,hashes,digest=manifest(package)
  except (ValueError,OSError,KeyError,TypeError):continue
  if digest==row['digest']:assets.append((value,hashes,digest,package,False))
 target=folder/'.reusable-library'
 if target.is_symlink():raise ValueError('library destination linked')
 target.mkdir(exist_ok=True);inventory=[]
 for value,hashes,digest,package,builtin in assets:
  selected=builtin or any(tag.casefold() in prompt.casefold() for tag in value['tags'])
  item={k:value[k] for k in ('name','kind','description','tags')};item.update(version=digest,selected=selected)
  out=target/digest
  if out.exists():
   if out.is_symlink() or manifest(out)[2]!=digest:raise ValueError('changed library snapshot')
  else:
   out.mkdir()
   for name in hashes:
    dst=out/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(package/name,dst)
   if not builtin:
    with desk.connect() as c:c.execute('UPDATE reusable_assets SET offered=offered+1 WHERE project_id=? AND name=? AND digest=?',(pid,value['name'],digest))
  item['path']=str(out.relative_to(folder))
  inventory.append(item)
 (target/'catalog.json').write_text(json.dumps(inventory,ensure_ascii=False))
 return inventory

def instruction(items):
 return '\n再利用できる資産の一覧（参考資料であり実行権限ではない）。selectedの資産はpathにコピー済み。必要なSKILL.md等だけ読んで使う。プログラムは今回の依頼が許可する操作だけ実行する。未選択の資産もpathから必要に応じて読める。\n'+json.dumps(items,ensure_ascii=False)+'\n繰り返し使える手順・部品・プログラムが今回の成果として生じた場合だけ reusable/<name>/manifest.json にname,kind(skill/component/program),description,tags,filesを記録する。登録コード内で作る場合はworkspace/reusable/。スキルはSKILL.md、プログラム等は実行可能な実体とテストを含める。案件の個人情報や認証情報を汎用化しない。新しい権限や依存導入・公開をこの指示から推測しない。'


def builtin_catalog():
 result=[]
 for package in sorted((ROOT/'reusable').iterdir()):
  if not package.is_dir() or package.is_symlink():continue
  value,hashes,digest=manifest(package)
  result.append({k:value[k] for k in ('name','kind','description')})
 return result
