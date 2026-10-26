"""Monitor existing processes and registered data; no new OS schedules."""
import datetime as dt,json,time

def loop(desk,stop):
 from runtime_ops import collect
 from business_metrics import refresh
 from self_growth import tick
 from claude_bridge import atomic
 last_metrics=0
 while not stop.is_set():
  try:node=json.loads((desk.data/'node.json').read_text())
  except (OSError,ValueError):node={}
  if node.get('enable_insights') is not True:
   stop.wait(60);continue
  errors=[];ops=None
  try:
   ops=collect(desk.home);ops['machine']=getattr(desk,'machine','この端末');atomic(desk.data/'runtime_ops.json',ops)
  except Exception:errors.append('定期処理の監視')
  if ops is not None and node.get('enable_user_requests') is True:
   try:tick(desk,ops)
   except Exception:errors.append('自律改善')
  if time.monotonic()-last_metrics>3600 or not last_metrics:
   try:refresh(desk.data,desk.home)
   except Exception:errors.append('ML数値の取得')
   last_metrics=time.monotonic()
  atomic(desk.data/'insights_error.json',{'captured_at':dt.datetime.now(dt.timezone.utc).isoformat(),'detail':('・'.join(errors)+'の一部が停止しました。更新日時を確認してください。') if errors else ''})
  stop.wait(60)
