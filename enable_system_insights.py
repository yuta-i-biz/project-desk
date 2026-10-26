"""Explicitly enable read-only monitoring and optional copy-only self-improvement."""
import argparse,json,os,shutil
from pathlib import Path
from claude_bridge import atomic

def enable(root,project_id=None,source=None,metrics=None):
 root=Path(root);data=root/'data';node=data/'node.json';settings=json.loads(node.read_text())
 if not (data/'desk.sqlite3').is_file():raise ValueError('runtime required')
 if project_id:
  from app import Desk
  desk=Desk(Path.home(),data);p=next((p for p in desk.collect()['projects'] if p['id']==project_id),None)
  if not p or p['name']!='Codex業務環境・全案件管理':raise ValueError('own app project required')
  from workspace import validate
  validated=validate(source,Path.home())
  if not all((validated/n).is_file() for n in ['app.py','test_app.py','execution.py']):raise ValueError('app code required')
 if metrics:
  path=Path(metrics)
  if path.is_symlink() or path.stat().st_size>64000:raise ValueError('invalid metrics registry')
  source_records=json.loads(path.read_text());records=[]
  for r in source_records:
   if r.get('company')!='モノ・ループ' or r.get('adapter')!='ml_planned' or r.get('sheet')!='実績DB' or type(r.get('row_count'))!=int or not 2<=r['row_count']<=50000:raise ValueError('verified ML source required')
   import re
   if not re.fullmatch(r'[A-Za-z0-9_-]{10,}',str(r.get('spreadsheet_id',''))):raise ValueError('invalid source')
   records.append({k:r[k] for k in ['company','adapter','sheet','row_count','spreadsheet_id']})
 # Keep an explicit reversible local backup, never include it in public source.
 backup=data/'insights_before_enable';backup.mkdir(mode=0o700,exist_ok=True)
 for name in ['node.json','self_growth.json','business_sources.json','workspace_sources.json']:
  p=data/name
  if p.exists() and not (backup/name).exists():shutil.copy2(p,backup/name);os.chmod(backup/name,0o600)
 if project_id:
  from workspace import register
  register(data,project_id,str(validated),Path.home());atomic(data/'self_growth.json',{'enabled':True,'project_id':project_id})
 if metrics:atomic(data/'business_sources.json',records)
 settings['enable_insights']=True;atomic(node,settings)
 return {'enabled':True,'self_growth':bool(project_id),'metrics_registered':bool(metrics),'scope':'作業コピーだけ。原本・本番反映なし。'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--project-id');p.add_argument('--source');p.add_argument('--metrics-registry');a=p.parse_args()
 print(json.dumps(enable(a.root,a.project_id,a.source,a.metrics_registry),ensure_ascii=False))
if __name__=='__main__':main()
