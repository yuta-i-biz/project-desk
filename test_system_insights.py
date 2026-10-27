import datetime as dt,json,plistlib,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from business_metrics import aggregate_ml,proposals,snapshot,JST
from runtime_ops import collect,parse_state
from app import Desk
import self_growth
class MetricsTests(unittest.TestCase):
 def test_partial_period_and_definition(self):
  now=dt.datetime(2026,10,27,tzinfo=JST);serial=(dt.date(2026,10,1)-dt.date(1899,12,30)).days
  rows=[['店','店舗',serial,'予定売上',100],['店','店舗',serial,'予定利益',40]]
  r=aggregate_ml(rows,now);self.assertTrue(r[0]['partial']);self.assertFalse(r[0]['closed_confirmed']);self.assertEqual(r[0]['values']['予定利益'],40);self.assertIn('確定売上',r[0]['definition']);self.assertEqual(proposals(r)[0]['kind'],'analysis_proposal')
  r=aggregate_ml(rows+[rows[0]],now);self.assertEqual(r[0]['values'],{});self.assertEqual(r[0]['status'],'ambiguous')
 def test_existing_mcp_formatted_cells(self):
  r=aggregate_ml([['店','店舗','2026/10/01','予定売上','6,101,937']],dt.datetime(2026,10,27,tzinfo=JST));self.assertEqual(r[0]['values']['予定売上'],6101937)
 def test_missing_is_not_zero_and_stale_not_current_proposal(self):
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp);r=snapshot(p,[{'company':'A'}]);self.assertEqual(r['companies'][0]['state'],'missing');self.assertEqual(r['companies'][0]['periods'],[])
   (p/'business_metrics.json').write_text(json.dumps({'companies':[{'company':'A','state':'observed','captured_at':'2020-01-01T00:00:00+00:00','proposals':[1]}]}));r=snapshot(p,[]);self.assertEqual(r['companies'][0]['state'],'stale');self.assertEqual(r['companies'][0]['proposals'],[])
 def test_nonfinite_or_missing_value_never_a_valid_sum(self):
  now=dt.datetime(2026,10,27,tzinfo=JST);serial=(dt.date(2026,10,1)-dt.date(1899,12,30)).days
  self.assertEqual(aggregate_ml([['店','店舗',serial,'予定利益','NaN']],now)[0]['values'],{})
  with self.assertRaises(ValueError):aggregate_ml([['店','店舗',serial,'予定利益']],now)
class CohortTests(unittest.TestCase):
 def test_same_store_channel_and_no_partial_comparison(self):
  from business_metrics import cohort_comparison
  rows=[]
  for month in ['2026/08/01','2026/09/01','2026/10/01']:
   for metric,value in [('予定売上',100),('予定利益',40 if '08' in month else 30),('買取件数',4)]:rows.append(['共通店','店舗',month,metric,value])
  rows.append(['新店','店舗','2026/09/01','予定利益',1000]);c=cohort_comparison(rows,dt.datetime(2026,10,27,tzinfo=JST));self.assertEqual(c['pairs'],1);self.assertEqual(c['after'],'2026-09');self.assertEqual(c['negative_pairs'],1);self.assertEqual(c['totals']['2026-09']['予定利益'],30)
class OpsTests(unittest.TestCase):
 def test_waiting_is_not_failed_and_no_raw_env_or_log(self):
  with tempfile.TemporaryDirectory() as temp:
   home=Path(temp);d=home/'Library/LaunchAgents';d.mkdir(parents=True);log=home/'log';log.write_text('SECRET_LOG')
   (d/'com.imagawa.test.plist').write_bytes(plistlib.dumps({'Label':'com.imagawa.test','EnvironmentVariables':{'SECRET':'SECRET_VALUE'},'StandardOutPath':str(log),'StartCalendarInterval':{'Hour':0,'Minute':5},'ProgramArguments':['/bin/bash',str(home/'missing-job.py')]}))
   r=collect(home,lambda *a,**kw:subprocess.CompletedProcess(a,0,'state = not running\nruns = 1\nlast exit code = 0',''))
   self.assertEqual(r['rows'][0]['status'],'idle');self.assertEqual(r['rows'][0]['missing_files'],['missing-job.py']);self.assertNotIn('SECRET',json.dumps(r));self.assertNotIn(str(log),json.dumps(r))
   r=collect(home,lambda *a,**kw:subprocess.CompletedProcess(a,0,'state = not running\nlast exit code = 1',''));self.assertEqual(r['rows'][0]['status'],'failed')
 def test_unreadable_state_is_not_success(self):self.assertIsNone(parse_state('unknown')['last_exit'])
class GrowthTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();root=Path(self.temp.name);self.home=root/'home';self.home.mkdir();self.desk=Desk(self.home,root/'data');self.pid=self.desk.mutate('project',{'company':'自分株式会社','name':'Codex業務環境・全案件管理'})['id']
  self.source=self.home/'code';self.source.mkdir()
  subprocess.run(['git','init','-q',str(self.source)],check=True)
  for n in ['app.py','execution.py','test_app.py']:(self.source/n).write_text('test fixture')
  subprocess.run(['git','-C',str(self.source),'add','.'],check=True);subprocess.run(['git','-c','user.name=Test','-c','user.email=test@example.invalid','-C',str(self.source),'commit','-qm','fixture'],check=True)
  (self.desk.data/'workspace_sources.json').write_text(json.dumps({self.pid:{'source':str(self.source),'mode':'copy','registered_locally':True}}));self.calls=[]
 def tearDown(self):self.temp.cleanup()
 def submit(self,desk,payload):
  self.calls.append(payload);ident='task-0123456789abcdef';(desk.data/'requests'/ident).mkdir(parents=True);return {'task_id':ident}
 def test_disabled_then_single_dispatch_and_holds_without_review(self):
  self_growth.tick(self.desk,{},self.submit);self.assertEqual(self.calls,[])
  (self.desk.data/'self_growth.json').write_text(json.dumps({'enabled':True,'project_id':self.pid}))
  self_growth.tick(self.desk,{},self.submit);self_growth.tick(self.desk,{},self.submit);self.assertEqual(len(self.calls),1)
  import execution
  self.assertIs(self.calls[0]['_self_growth'],execution.SELF_GROWTH);self.assertTrue(self.calls[0]['_autonomous'])
  p=self.desk.data/'requests/task-0123456789abcdef/receipt.json';p.write_text(json.dumps({'execution_status':'succeeded','review':{'status':'unverified'},'workspace':{'original_unchanged':True}}));self_growth.tick(self.desk,{},self.submit)
  self.assertEqual(self_growth.status(self.desk)['runs'][0]['state'],'held');self_growth.tick(self.desk,{},self.submit);self.assertEqual(len(self.calls),1)
 def test_success_is_ready_for_review_not_auto_deployed(self):
  (self.desk.data/'self_growth.json').write_text(json.dumps({'enabled':True,'project_id':self.pid}));self_growth.tick(self.desk,{},self.submit)
  (self.desk.data/'requests/task-0123456789abcdef/receipt.json').write_text(json.dumps({'execution_status':'succeeded','review':{'status':'reviewed'},'workspace':{'original_unchanged':True}}));self_growth.tick(self.desk,{},self.submit)
  self.assertEqual(self_growth.status(self.desk)['runs'][0]['state'],'ready');self.assertEqual((self.source/'app.py').read_text(),'test fixture')
 def test_uncertain_dispatch_never_replayed(self):
  self_growth.init(self.desk)
  with self.desk.connect() as c:c.execute("INSERT INTO self_growth_runs(fingerprint,task_id,state,reason,created) VALUES('f',NULL,'dispatching','uncertain','2026-10-27')")
  (self.desk.data/'self_growth.json').write_text(json.dumps({'enabled':True,'project_id':self.pid}));self_growth.tick(self.desk,{},self.submit);self.assertEqual(self.calls,[]);self.assertEqual(self_growth.status(self.desk)['runs'][0]['state'],'held')
class IterativeGrowthTests(unittest.TestCase):
 setUp=GrowthTests.setUp
 tearDown=GrowthTests.tearDown
 def submit_next(self,desk,payload):
  self.calls.append(payload);ident='task-'+format(len(self.calls),'016x');(desk.data/'requests'/ident).mkdir(parents=True);return {'task_id':ident}
 def test_chain_carries_parent_and_stops_after_three(self):
  (self.desk.data/'self_growth.json').write_text(json.dumps({'enabled':True,'project_id':self.pid}));self_growth.tick(self.desk,{},self.submit_next)
  for iteration in range(1,4):
   ident='task-'+format(iteration,'016x');(self.desk.data/'requests'/ident/'receipt.json').write_text(json.dumps({'execution_status':'succeeded','review':{'status':'reviewed'},'workspace':{'original_unchanged':True,'changed_files':['app.py']}}));self_growth.tick(self.desk,{},self.submit_next)
  self.assertEqual(len(self.calls),3);self.assertEqual(self.calls[1]['_growth_parent'],'task-0000000000000001');self.assertEqual(self.calls[2]['_growth_parent'],'task-0000000000000002')
  runs=self_growth.status(self.desk)['runs'];self.assertEqual(sum(r['state']=='ready' for r in runs),1);self.assertEqual(sum(r['state']=='superseded' for r in runs),2);self_growth.tick(self.desk,{},self.submit_next);self.assertEqual(len(self.calls),3)
 def test_prior_copy_preserves_edits_additions_deletions(self):
  from workspace import prepare,prepare_previous,report,record_manifest
  self_growth.init(self.desk);t=self.desk.mutate('create',{'project_id':self.pid,'title':'first','next_action':'test'});parent=self.desk.data/'requests'/t['id'];parent.mkdir(parents=True);manifest=prepare(self.desk,self.pid,parent);record_manifest(self.desk,self.pid,parent,manifest)
  # A model-written metadata file must not replace the host's stored provenance.
  (parent/'workspace_manifest.json').write_text('{}')
  with self.desk.connect() as c:c.execute("INSERT INTO self_growth_runs(fingerprint,task_id,state,reason,created) VALUES('owned',?,'superseded','next','2026-10-27')",(t['id'],))
  (parent/'workspace/app.py').write_text('improved');(parent/'workspace/execution.py').unlink();(parent/'workspace/new.txt').write_text('new');(parent/'receipt.json').write_text(json.dumps({'execution_status':'succeeded','review':{'status':'issues'},'workspace':{'original_unchanged':True}}))
  child=self.desk.data/'requests/child';child.mkdir();copied=prepare_previous(self.desk,self.pid,child,t['id']);self.assertEqual((child/'workspace/app.py').read_text(),'improved');self.assertFalse((child/'workspace/execution.py').exists());self.assertEqual((child/'workspace/new.txt').read_text(),'new');self.assertEqual((self.source/'app.py').read_text(),'test fixture');self.assertEqual(set(report(copied,child)['changed_files']),{'app.py','execution.py','new.txt'})
class InitiativeTests(unittest.TestCase):
 def test_only_ml_and_no_effect_claim(self):
  from initiatives import report
  r=report([{'id':'p','company':'モノ・ループ','name':'クーポン'},{'id':'q','company':'Shake','name':'施策'}],[{'project_id':'p','status':'未着手','start_date':'2026-10-01'}]);self.assertEqual(len(r['rows']),1);self.assertEqual(r['rows'][0]['planned_start'],'2026-10-01');self.assertIn('施策効果は未検証',r['rows'][0]['assessment']);self.assertEqual(r['rows'][0]['candidate_measures'][0],'配布枚数')
 def test_completed_project_is_not_an_active_initiative(self):
  from initiatives import report
  self.assertEqual(report([{'id':'p','company':'モノ・ループ','name':'クーポン'}],[{'project_id':'p','status':'完了'}])['rows'],[])
if __name__=='__main__':unittest.main()
