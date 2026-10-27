"""Reuse only host-stored independent findings with unchanged code and rules."""
import hashlib,json,re,sqlite3
from pathlib import Path
from contextlib import closing

def setup(folder,prompt,job,files):
 if job.get('kind') not in ('implementation','editing') or not job.get('registered_workspace'):return None
 if folder.parent.name!='requests' or not re.fullmatch('task-[a-f0-9]{16}',folder.name):return None
 data=folder.parent.parent;db=data/'desk.sqlite3'
 if db.is_symlink() or not db.is_file():return None
 evidence=job.get('isolated_test_evidence',{})
 if evidence.get('status')!='passed' or not evidence.get('manifest'):return None
 with closing(sqlite3.connect(db)) as c,c:
  owner=c.execute('SELECT project_id FROM tasks WHERE id=?',(folder.name,)).fetchone()
  if not owner:return None
  c.execute('CREATE TABLE IF NOT EXISTS independent_review_cache(cache_key TEXT PRIMARY KEY,task_id TEXT,checks TEXT,hashes TEXT)')
 refs=job.get('_reference_hashes')
 if not refs:return None
 # Any code/configuration change invalidates all code findings; dependency
 # impact is deliberately conservative. Reports can still be checked alone.
 key=hashlib.sha256(json.dumps([owner[0],job.get('_review_contract',prompt),job['kind'],refs,evidence['manifest'],hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),hashlib.sha256(Path(__file__).with_name('review.py').read_bytes()).hexdigest()],sort_keys=True).encode()).hexdigest()
 hashes={}
 for f in files:
  path=folder/f['name']
  if path.is_file() and not path.is_symlink():hashes[f['name']]=hashlib.sha256(path.read_bytes()).hexdigest()
 if (folder/'response.txt').is_file():hashes['response.txt']=hashlib.sha256((folder/'response.txt').read_bytes()).hexdigest()
 with closing(sqlite3.connect(db)) as c,c:row=c.execute('SELECT task_id,checks,hashes FROM independent_review_cache WHERE cache_key=?',(key,)).fetchone()
 reused=[]
 if row:
  checks=json.loads(row[1]);old=json.loads(row[2])
  reused=[{**check,'reused_from_task':row[0]} for check in checks if old.get(check['file'])==hashes.get(check['file']) and check['file'] in hashes and check['file']!='response.txt']
 return {'db':db,'key':key,'task':folder.name,'hashes':hashes,'reused':reused}

def run(folder,prompt,job,engines,env,files,reviewer):
 plan=setup(folder,prompt,job,files)
 if plan is None:return reviewer(folder,prompt,job,engines,env,files)
 reused=plan['reused'];names={c['file'] for c in reused}
 remaining=[f for f in files if f['name'] not in names]
 result=reviewer(folder,prompt,job,engines,env,remaining)
 # The read-only reviewer must never modify even files skipped by the cache.
 for name,digest in plan['hashes'].items():
  p=folder/name
  if not p.is_file() or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:return {'status':'unverified','independent':False,'checks':[],'summary':'差分検品中に成果物が変化したため無効にしました。'}
 result['checks']=result.get('checks',[])+reused
 result['reused_checks']=len(reused);result['fresh_checks']=len(result['checks'])-len(reused)
 if reused:result['summary']='前回の独立検品から変更のない'+str(len(reused))+'件を引継ぎ。テストは今回も実行。'+result.get('summary','')
 covered={c['file'] for c in result['checks']}
 if result.get('status')=='reviewed' and set(plan['hashes'])-covered:result.update(status='unverified',summary='差分検品の対象漏れがあります。')
 if result.get('status')=='reviewed' and result.get('independent') is True:
  checks=[{k:v for k,v in c.items() if k!='reused_from_task'} for c in result['checks']]
  with closing(sqlite3.connect(plan['db'])) as c,c:c.execute('INSERT OR REPLACE INTO independent_review_cache VALUES(?,?,?,?)',(plan['key'],plan['task'],json.dumps(checks,ensure_ascii=False),json.dumps(plan['hashes'])))
 return result
