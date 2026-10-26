"""Link ML projects to measurement questions, never claim causal uplift."""
import datetime as dt,re
JST=dt.timezone(dt.timedelta(hours=9))
MEASURES=[(('クーポン',),['配布枚数','回収枚数','クーポン経由の予定利益']), (('チラシ','PT','ビラ'),['配布枚数','投入時間・費用','戻り人数','経由する利益']), (('査定','買取'),['接客件数','成約率','一件あたりの利益','査定に要する時間']), (('採用','人事','勤怠'),['必要人数に対する充足','欠員・残業','人件費と業務量'])]
def report(projects,tasks):
 rows=[]
 for p in projects:
  if p.get('company')!='モノ・ループ' or p.get('reference_only'):continue
  ts=[t for t in tasks if t.get('project_id')==p['id']];pending=[t for t in ts if t.get('status')!='完了']
  if ts and not pending:continue
  title=p['name'];suggested=next((metrics for keys,metrics in MEASURES if any(k in title for k in keys)),[])
  rows.append({'project_id':p['id'],'title':title,'open_tasks':len(pending),'waiting_tasks':sum(t.get('status') in ('確認待ち','保留') for t in pending),'planned_start':min((t['start_date'] for t in ts if re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(t.get('start_date','')))),default=None),'candidate_measures':suggested,'assessment':'施策効果は未検証。実施開始日・対象店舗・実施量・費用・比較対象と結果の対応が必要です。','next_action':p.get('next_action','')})
 return {'rows':rows,'scope':'MLの案件・タスク記録を施策の検証候補として表示。案件数は施策実施数ではありません。','caution':'複数施策・店舗構成・季節性・金相場などを分けず、全社数値の増減を個別施策の効果と断定しません。'}
