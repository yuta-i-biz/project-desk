import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from app import Desk
import execution
class CrossChatTests(unittest.TestCase):
 def test_scoped_and_global_context_and_reused_project(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);d=Desk(root/'home',root/'data');(d.data/'engines.json').write_text(json.dumps([{'engine':'Codex','available':True}]))
   a=d.mutate('project',{'name':'甲','company':'A'})['id'];b=d.mutate('project',{'name':'乙','company':'B'})['id']
   ta=d.mutate('create',{'project_id':a,'title':'Aの作業','next_action':'A'})['id'];tb=d.mutate('create',{'project_id':b,'title':'Bの作業','next_action':'B'})['id']
   with patch.object(execution.POOL,'submit'):
    one=execution.submit(d,{'project_id':a,'prompt':'整理して'});context=json.loads((d.data/'requests'/one['task_id']/'project_context.json').read_text());self.assertIn(ta,[t['id'] for t in context['tasks']]);self.assertNotIn(tb,[t['id'] for t in context['tasks']])
    both=execution.submit(d,{'project_id':'__all__','prompt':'全体を整理して'});context=json.loads((d.data/'requests'/both['task_id']/'project_context.json').read_text());self.assertIn(ta,[t['id'] for t in context['tasks']]);self.assertIn(tb,[t['id'] for t in context['tasks']]);execution.submit(d,{'project_id':'__all__','prompt':'続けて整理して'})
   self.assertEqual(sum(p['name']=='全案件の横断チャット' for p in d.snapshot()['projects']),1)
 def test_receipt_applies_explicit_change(self):
  import subprocess
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);d=Desk(root/'home',root/'data');(d.data/'engines.json').write_text(json.dumps([{'engine':'Codex','available':True}]))
   p=d.mutate('project',{'name':'甲','company':'A'})['id'];t=d.mutate('create',{'project_id':p,'title':'調査タスク','next_action':'調査'})
   quote='調査タスクの期日を2026-11-02に変更'
   def runner(command,**kw):
    if command[1:3]==['login','status']:return subprocess.CompletedProcess(command,0,'Logged in using ChatGPT','')
    folder=kw['cwd'];(folder/'response.txt').write_text('更新案を作成しました。');(folder/'schedule_updates.json').write_text(json.dumps([{'task_id':t['id'],'source_quote':quote,'due_date':'2026-11-02'}]));return subprocess.CompletedProcess(command,0)
   with patch.object(execution.POOL,'submit',side_effect=lambda fn:fn()),patch.object(execution.subprocess,'run',side_effect=runner):r=execution.submit(d,{'project_id':p,'prompt':quote})
   task=next(x for x in d.snapshot()['tasks'] if x['id']==t['id']);self.assertEqual(task['due_date'],'2026-11-02');receipt=json.loads((d.data/'requests'/r['task_id']/'receipt.json').read_text());self.assertTrue(receipt['schedule_updates'][0]['applied'])
