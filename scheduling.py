"""Validate dates and project-local task dependencies without inventing deadlines."""
import datetime as dt
FIELDS=('due_date','start_date','effort_days','depends_on','deadline_reason','completion_criteria')
def validate(c,payload,pid,tid,current=None):
    values={k:payload.get(k,current[k] if current is not None else '') for k in FIELDS}
    for k,v in values.items():
        if not isinstance(v,str) or len(v)>2000:raise ValueError('日程の入力を確認してください。')
        values[k]=v.strip()
    for k in ('due_date','start_date'):
        if values[k]:
            try:
                if len(values[k])!=10:raise ValueError()
                dt.date.fromisoformat(values[k])
            except ValueError:raise ValueError('日付はYYYY-MM-DDで入力してください。')
    if values['due_date'] and values['start_date'] and values['start_date']>values['due_date']:raise ValueError('開始日は期日より前にしてください。')
    if values['effort_days']:
        try:
            n=float(values['effort_days'])
            if not 0<n<=3650:raise ValueError()
        except ValueError:raise ValueError('所要日数は0より大きい数値で入力してください。')
    pred=values['depends_on'];seen={tid}
    while pred:
        if pred in seen:raise ValueError('前工程が循環しています。')
        seen.add(pred);row=c.execute('SELECT project_id,depends_on FROM tasks WHERE id=?',(pred,)).fetchone()
        if row is None or row['project_id']!=pid:raise ValueError('前工程は同じ案件のタスクを選んでください。')
        pred=row['depends_on']
    return values
