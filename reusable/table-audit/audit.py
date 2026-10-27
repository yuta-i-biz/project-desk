"""Deterministic CSV audit. Never modify source data or conceal invalid values."""
import argparse,csv,json
from decimal import Decimal,InvalidOperation
from pathlib import Path

def audit(path,key=None,amount=None):
 with Path(path).open(encoding='utf-8-sig',newline='') as stream:
  reader=csv.DictReader(stream);headers=reader.fieldnames
  if not headers or len(set(headers))!=len(headers):raise ValueError('missing or duplicate headers')
  if any(name and name not in headers for name in (key,amount)):raise ValueError('specified column missing')
  count=0;seen=set();duplicate_rows=[];missing_keys=[];missing_amounts=[];invalid_amounts=[];total=Decimal(0)
  for line,row in enumerate(reader,2):
   if None in row or any(value is None for value in row.values()):raise ValueError('row width mismatch at '+str(line))
   count+=1
   if key:
    value=row[key].strip()
    if not value:missing_keys.append(line)
    elif value in seen:duplicate_rows.append(line)
    else:seen.add(value)
   if amount:
    value=row[amount].strip()
    if not value:missing_amounts.append(line);continue
    try:
     number=Decimal(value.replace(',',''))
     if not number.is_finite():raise InvalidOperation
     total+=number
    except InvalidOperation:invalid_amounts.append(line)
 return {'rows':count,'duplicate_rows':duplicate_rows,'missing_keys':missing_keys,'missing_amounts':missing_amounts,'invalid_amounts':invalid_amounts,'sum_of_valid_values':str(total) if amount else None,'sum_complete':not missing_amounts and not invalid_amounts if amount else None,'source_modified':False}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('file',type=Path);p.add_argument('--key');p.add_argument('--amount');a=p.parse_args();print(json.dumps(audit(a.file,a.key,a.amount),ensure_ascii=False))
