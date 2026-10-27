"""Read only the host-created reference snapshots in a request folder."""
import argparse,hashlib,json
from pathlib import Path

def read(root,ident=None,query=None,offset=0,length=12000):
 if offset<0 or length<1:raise ValueError('positive paging required')
 root=Path(root).resolve();store=root/'.reference-materials'
 if store.is_symlink():raise ValueError('linked reference store')
 records=json.loads((store/'index.json').read_text())
 if ident is None:return [{k:d[k] for k in ('id','name','kind','full_bytes')} for d in records]
 record=next(d for d in records if d['id']==ident);path=root/record['full_path']
 if path.is_symlink() or path.resolve().parent!=store.resolve():raise ValueError('out of scope reference')
 raw=path.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=record['full_sha256']:raise ValueError('changed reference')
 text=raw.decode();items=[{'line':i+1,'text':line} for i,line in enumerate(text.splitlines()) if query.casefold() in line.casefold()] if query is not None else text
 end=min(offset+length,len(items))
 return {'content':items[offset:end],'next_offset':end,'done':end==len(items),'total':len(items)}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--list',action='store_true');p.add_argument('--id');p.add_argument('--query');p.add_argument('--offset',type=int,default=0);p.add_argument('--length',type=int,default=12000);a=p.parse_args()
 print(json.dumps(read(a.root,None if a.list else a.id,a.query,a.offset,a.length),ensure_ascii=False))
