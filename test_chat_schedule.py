import unittest,tempfile
from pathlib import Path
from app import Desk
from chat_schedule import apply,overlay

class ScheduleChatTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name);self.d=Desk(root/'home',root/'data');self.p=self.d.mutate('project',{'name':'案件A','company':'会社A'})['id'];self.q=self.d.mutate('project',{'name':'案件B','company':'会社B'})['id'];self.t=self.d.mutate('create',{'project_id':self.p,'title':'調査タスク','next_action':'調査する'});self.snap=self.d.snapshot()['tasks']
 def tearDown(self):self.temp.cleanup()
 def test_explicit_date_and_completion(self):
  quote='調査タスクの期日を2026/11/2に変更';r=apply(self.d,self.p,quote,[{'task_id':self.t['id'],'source_quote':quote,'due_date':'2026-11-02'}],self.snap);self.assertTrue(r[0]['applied']);self.assertEqual(self.d.snapshot()['tasks'][0]['due_date'],'2026-11-02')
  quote='調査タスクは完了';r=apply(self.d,self.p,quote,[{'task_id':self.t['id'],'source_quote':quote,'status':'完了'}],self.d.snapshot()['tasks']);self.assertTrue(r[0]['applied'])
 def test_other_project_and_unquoted_and_negated(self):
  for pid,quote,req in [(self.q,'調査タスクは完了','調査タスクは完了'),(self.p,'調査タスクは完了','確認して'),(self.p,'調査タスクは完了に変更しない','調査タスクは完了に変更しない'),(self.p,'調査タスクは未完了','調査タスクは未完了')]:
   r=apply(self.d,pid,req,[{'task_id':self.t['id'],'source_quote':quote,'status':'完了'}],self.snap);self.assertFalse(r[0]['applied'])
 def test_conflict_and_date_invention(self):
  quote='調査タスクの期日を2026-11-02に変更';r=apply(self.d,self.p,quote,[{'task_id':self.t['id'],'source_quote':quote,'due_date':'2026-11-03'}],self.snap);self.assertFalse(r[0]['applied']);self.d.mutate('update',{'id':self.t['id'],'version':1,'status':'未着手','next_action':'別の作業'});r=apply(self.d,self.p,quote,[{'task_id':self.t['id'],'source_quote':quote,'due_date':'2026-11-02'}],self.snap);self.assertFalse(r[0]['applied'])
 def test_readonly_override_without_source_change(self):
  t={'id':'sheet-1','project_id':self.p,'title':'原本の仕事','status':'未着手','read_only':True,'version':None,'deadline':'2026/10/25(日)'}
  original=self.d.snapshot;self.d.snapshot=lambda:{'tasks':overlay(self.d,[t])};quote='原本の仕事の期日を2026-11-02に変更';r=apply(self.d,self.p,quote,[{'task_id':t['id'],'source_quote':quote,'due_date':'2026-11-02'}],[t]);self.assertTrue(r[0]['applied']);self.assertEqual(t['deadline'],'2026/10/25(日)');self.assertEqual(overlay(self.d,[t])[0]['due_date'],'2026-11-02');self.d.snapshot=original
 def test_duplicate_project_rejected(self):
  with self.assertRaises(ValueError):self.d.mutate('project',{'name':'案件A','company':'会社A'})
