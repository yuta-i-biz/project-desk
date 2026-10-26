import datetime as dt,json,tempfile,unittest
from pathlib import Path
from autonomy import report,classify,safe_url,JST
class AutonomyTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.now=dt.datetime(2026,10,27,12,tzinfo=JST)
 def tearDown(self):self.temp.cleanup()
 def write(self,name,value,date='2026-10-26'):
  p=self.root/name;p.mkdir(exist_ok=True);f=p/(date+'.json');f.write_text(json.dumps(value));return f
 def test_failed_ai_is_not_assigned_to_person(self):
  self.assertEqual(classify({}, {'final_status':'要人力'}),'repair');self.assertEqual(classify({}, {'final_status':'要データ'}),'data')
 def test_source_namespace_and_date_isolation(self):
  self.write('task_triage',{'date':'2026-10-26','tasks':[{'id':'1','source':'candidate','タスク名':'調査','triage':{'category':'auto_run'}}]})
  self.write('night_exec',{'date':'2026-10-26','results':[{'task_id':'1','source':'gantt','final_status':'済'}]})
  self.assertEqual(report(self.root,now=self.now)['rows'][0]['group'],'ai')
  self.write('night_exec',{'date':'2026-10-25','results':[{'task_id':'1','source':'candidate','final_status':'済'}]})
  self.assertFalse(report(self.root,now=self.now)['date_match'])
  self.assertEqual(report(self.root,now=self.now)['rows'][0]['group'],'ai')
 def test_approval_and_url(self):
  self.write('task_triage',{'date':'2026-10-26','tasks':[{'id':'1','source':'gantt','タスク名':'分析','triage':{}}]})
  self.write('night_exec',{'date':'2026-10-26','results':[{'task_id':'1','source':'gantt','final_status':'コピー承認待ち','url':'https://docs.google.com/document/d/1/edit'}]})
  r=report(self.root,now=self.now)['rows'][0];self.assertEqual(r['group'],'approval');self.assertTrue(r['url'])
  self.assertEqual(safe_url('javascript:alert(1)'), '');self.assertEqual(safe_url('https://evil.example/a'),'')
 def test_missing_unclassified_dedup_and_no_title_guess(self):
  tasks=[{'id':'1','title':'分析','project_id':'p','status':'未着手'},{'id':'import','title':'分析','status':'未着手'},{'id':'2','title':'完了済み','status':'完了'}]
  r=report(self.root,[{'id':'p'}],tasks,self.now);self.assertEqual(len(r['unclassified']),1);self.assertEqual(r['unclassified'][0]['project_id'],'p');self.assertEqual(r['sources'][0]['state'],'missing')
 def test_ambiguous_project_not_guessed(self):
  self.write('task_triage',{'tasks':[{'id':'1','タスク名':'分析'}]})
  r=report(self.root,[{'id':'a'},{'id':'b'}],[{'title':'分析','project_id':'a'},{'title':'分析','project_id':'b'}],self.now)
  self.assertIsNone(r['rows'][0]['project_id'])
 def test_unsupported_or_unsafe_source_is_visible(self):
  self.write('task_triage',[]);self.assertEqual(report(self.root,now=self.now)['sources'][2]['state'],'error')
  p=self.write('plaud_fetch',{});p.unlink();p.symlink_to(self.root/'task_triage/2026-10-26.json');self.assertEqual(report(self.root,now=self.now)['sources'][0]['state'],'error')
 def test_meeting_type_evidence_preserved(self):
  self.write('plaud_llm',{'extracted_recordings':[{'ok':True,'tasks':[{'type':'検討課題','task_content':'検討する','source_utterance':'検討しよう'}]}]})
  r=report(self.root,now=self.now);self.assertEqual(r['meetings'][0]['tasks'][0]['type'],'検討課題');self.assertEqual(r['rows'],[])
if __name__=='__main__':unittest.main()
