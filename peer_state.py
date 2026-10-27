"""Freshness and differences of read-only device records, never a merge writer."""
import datetime as dt

def freshness(status,captured_at,now=None):
 now=now or dt.datetime.now(dt.timezone.utc)
 stamp=status.get('last_success') or captured_at
 try:
  date=dt.datetime.fromisoformat(stamp)
  if date.tzinfo is None:raise ValueError('timezone missing')
  age=(now-date).total_seconds()
 except (ValueError,TypeError):return {**status,'state':'unknown','fresh':False,'age_seconds':None}
 interval=status.get('interval_seconds',120)
 if not isinstance(interval,int) or isinstance(interval,bool) or interval<1:interval=120
 fresh=0<=age<=max(360,3*interval) and status.get('ok') is True
 return {**status,'state':'fresh' if fresh else 'stale','fresh':fresh,'age_seconds':round(age),'last_success':stamp}

def differences(sources):
 records=[s for s in sources if s.get('type')=='案件台帳']
 result=[]
 for field in ('現在地','次アクション','未解決'):
  rows=[{'machine':s.get('machine','未確認'),'updated':s.get('updated'),'value':s.get('sections',{}).get(field),'source_id':s['id']} for s in records if s.get('sections',{}).get(field)]
  if len({r['machine'] for r in rows})>1 and len({' '.join(r['value'].split()) for r in rows})>1:result.append({'field':field,'records':rows})
 return result
