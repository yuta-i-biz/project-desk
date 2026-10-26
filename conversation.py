"""User-approved context: at most three completed responses in the same project."""
import json,re

def history(desk,project_id,exclude=''):
    result=[]
    with desk.connect() as c:
        rows=c.execute('SELECT id,title,created FROM tasks WHERE project_id=? AND id!=? ORDER BY created DESC,rowid DESC',(project_id,exclude)).fetchall()
    for task in rows:
        if not re.fullmatch(r'task-[0-9a-f]+',task['id']):continue
        p=desk.data/'requests'/task['id']/'receipt.json'
        try:r=json.loads(p.read_text())
        except (OSError,ValueError):continue
        answer=r.get('summary','');request=r.get('request',task['title'])
        if not isinstance(answer,str) or not isinstance(request,str) or not answer.strip():continue
        result.append({'task_id':task['id'],'request':request[:1500],'response':answer[:2500]})
        if len(result)==3:break
    return list(reversed(result))
