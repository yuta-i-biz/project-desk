"""Derive AI progress from recorded evidence, not generic confirmation text."""
import sqlite3,datetime

def classify(receipt,recorded_status=None,growth_state=None):
 review=receipt.get('review',{});workspace=receipt.get('workspace') or {}
 if growth_state=='superseded':return {'status':'完了','label':'次の改善へ引継ぎ済み','owner':'AI','next_action':'次の改善回の結果を確認する。','blocker':''}
 if receipt.get('execution_status')=='failed':return {'status':'保留','label':'AIの実行に失敗','owner':'AI','next_action':'AI側で実行記録と失敗原因を確認する。','blocker':receipt.get('unresolved') or 'AIの実行が正常終了していません。'}
 if review.get('status') in ('issues','unverified'):
  return {'status':'保留','label':'AI側の修正が必要' if review['status']=='issues' else 'AI側の検証が未完了','owner':'AI','next_action':'AI側で指摘を解消して検品する。' if review['status']=='issues' else 'AI側で不足した検証を完了する。','blocker':review.get('summary') or '独立検品が未完了です。'}
 if review.get('status') not in ('reviewed','not_required'):return {'status':'保留','label':'AI側の検品結果を確認中','owner':'AI','next_action':'検品結果の記録を確認する。','blocker':'検品結果を確認できません。'}
 if workspace.get('changed_files') and recorded_status!='完了':return {'status':'確認待ち','label':'検品済み・反映判断待ち','owner':'今川さん','next_action':'検品済みの変更案を本番に反映するか判断する。','blocker':'検品は完了しています。原本・本番へ反映する判断が必要です。'}
 return {'status':'完了','label':'検品済み・作業完了' if review.get('status')=='reviewed' else '回答作成完了','owner':'なし','next_action':'成果物または回答を確認できます。','blocker':''}

def decorate(desk,tasks):
 try:
  with desk.connect() as c:growth={r['task_id']:r['state'] for r in c.execute('SELECT task_id,state FROM self_growth_runs')}
 except sqlite3.OperationalError:growth={}
 for task in tasks:
  if not task.get('is_ai_request') or not isinstance(task.get('receipt'),dict):continue
  receipt_path=desk.data/'requests'/task['id']/'receipt.json'
  if task['status']=='作業中' and receipt_path.is_file() and datetime.datetime.fromisoformat(task['updated']).timestamp()>receipt_path.stat().st_mtime:
   task['execution_progress']={'label':'実行記録の更新が必要' if task.get('needs_check') else 'AIが再検証中（進行記録あり）','owner':'AI'}
   continue
  progress=classify(task['receipt'],task['status'],growth.get(task['id']))
  task.update(recorded_status=task['status'],execution_progress=progress,status=progress['status'],next_action=progress['next_action'],blocker=progress['blocker'],needs_check=False)
 return tasks
