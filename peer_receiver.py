"""SSH-only receiver: replace Project Desk caches, never original Claude records."""
import hashlib,json,os,re,tempfile,fcntl,datetime
from pathlib import Path

def fingerprint(snapshot):
 return hashlib.sha256(json.dumps({k:v for k,v in snapshot.items() if k!='captured_at'},sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def atomic(path,value):
 if path.is_symlink():raise ValueError('linked destination')
 fd,name=tempfile.mkstemp(prefix='.peer-write-',dir=path.parent)
 try:
  with os.fdopen(fd,'w') as stream:json.dump(value,stream,ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)

def receive(data,envelope):
 data=Path(data)
 if data.is_symlink() or not (data/'desk.sqlite3').is_file():raise ValueError('Project Desk data required')
 if envelope.get('machine')!='MacBook' or not re.fullmatch('[a-f0-9]{64}',str(envelope.get('fingerprint',''))):raise ValueError('invalid sender')
 lock=data/'.peer-sync.lock'
 if lock.is_symlink():raise ValueError('linked lock')
 with lock.open('a') as stream:
  fcntl.flock(stream,fcntl.LOCK_EX)
  path=data/'peer_snapshot.json';old={}
  if path.is_symlink():raise ValueError('linked snapshot')
  if path.exists():old=json.loads(path.read_text())
  captured=datetime.datetime.fromisoformat(envelope['captured_at'])
  if captured.tzinfo is None:raise ValueError('capture timezone required')
  if old.get('captured_at') and datetime.datetime.fromisoformat(old['captured_at'])>captured:raise ValueError('older snapshot rejected')
  snapshot=envelope.get('snapshot')
  if snapshot is None:
   if old.get('_fingerprint')!=envelope['fingerprint']:return {'needs_full':True}
   for src in old.get('sources',[]):
    ref=src.get('peer_document')
    if ref:
     file=data/'peer_documents'/(ref['sha256']+'.md')
     if file.is_symlink() or not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=ref['sha256']:return {'needs_full':True}
   snapshot=old;snapshot['captured_at']=envelope['captured_at']
  else:
   if snapshot.get('machine')!='MacBook' or snapshot.get('errors') or fingerprint(snapshot)!=envelope['fingerprint']:raise ValueError('invalid or incomplete snapshot')
   sources={s['id']:s for s in snapshot['sources']}
   documents=snapshot.pop('documents',[]);root=data/'peer_documents'
   expected={s['id'] for s in sources.values() if s.get('type')=='案件台帳'}
   if len(documents)!=len(expected) or {d.get('source_id') for d in documents}!=expected:raise ValueError('reference coverage incomplete')
   if root.is_symlink():raise ValueError('linked documents')
   for doc in documents:
    if doc.get('source_id') not in sources or not isinstance(doc.get('text'),str) or hashlib.sha256(doc['text'].encode()).hexdigest()!=doc.get('sha256'):raise ValueError('invalid reference')
   root.mkdir(mode=0o700,exist_ok=True)
   for doc in documents:
    dst=root/(doc['sha256']+'.md')
    if dst.is_symlink():raise ValueError('linked reference')
    if not dst.exists() or hashlib.sha256(dst.read_bytes()).hexdigest()!=doc['sha256']:
     fd,name=tempfile.mkstemp(prefix='.reference-',dir=root)
     with os.fdopen(fd,'w') as out:out.write(doc['text'])
     os.replace(name,dst)
    sources[doc['source_id']]['peer_document']={'sha256':doc['sha256'],'captured_at':envelope['captured_at'],'machine':'MacBook'}
   # This sender manages Claude records only. Keep existing Codex metadata.
   snapshot['sessions']+= [s for s in old.get('sessions',[]) if s.get('type')!='Claude Code' and s['id'] not in {x['id'] for x in snapshot['sessions']}]
   if old:atomic(data/'.peer_snapshot.previous.json',old)
  snapshot['_fingerprint']=envelope['fingerprint']
  snapshot['captured_at']=envelope['captured_at']
  for source in snapshot.get('sources',[]):
   if source.get('peer_document'):source['peer_document']['captured_at']=envelope['captured_at']
  atomic(path,snapshot)
  atomic(data/'peer_sync.json',{'ok':True,'machine':'MacBook','attempted_at':envelope['captured_at'],'last_success':envelope['captured_at'],'interval_seconds':120,'automatic':envelope.get('automatic') is True,'scope':'Claude Code台帳全文の参照コピーと会話の一覧情報。原本変更なし。'})
  return {'ok':True,'sources':len(snapshot['sources']),'sessions':len(snapshot['sessions']),'fingerprint':envelope['fingerprint']}

if __name__=='__main__':
 import sys
 print(json.dumps(receive(Path.home()/'Documents/Codex/project-desk/data',json.load(sys.stdin)),ensure_ascii=False))
