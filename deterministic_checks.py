"""Fixed read-only attachment checks shared by every AI provider."""
import importlib.util
from pathlib import Path

def load(name,file):
 spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parent/'reusable'/file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def inspect(folder):
 inventory=load('desk_fixed_inventory','file-inventory/inventory.py').inventory(folder)
 audit=load('desk_fixed_csv','table-audit/audit.py').audit
 tables=[]
 for row in inventory['files']:
  if Path(row['file']).suffix.lower()!='.csv':continue
  try:tables.append({'file':row['file'],'result':audit(Path(folder)/row['file'])})
  except (OSError,ValueError,UnicodeError) as e:tables.append({'file':row['file'],'state':'unverified','reason':type(e).__name__})
 return {'source':'検証済みの固定プログラム。添付プログラムは実行しない。','inventory':inventory,'csv_checks':tables}
