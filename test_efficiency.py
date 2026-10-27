import hashlib,importlib.util,json,tempfile,unittest
from pathlib import Path
from app import Desk
from execution_progress import classify
from usage_meter import counter,snapshot
from review_cache import run as review_run
from deterministic_checks import inspect,load

class UsageTests(unittest.TestCase):
 def test_provider_counter_semantics_and_unknowns(self):
  c=counter({'type':'turn.completed','usage':{'input_tokens':100,'cached_input_tokens':80,'output_tokens':3}},'Codex');self.assertEqual(c['input_tokens'],100);self.assertEqual(c['cached_input_tokens'],80)
  c=counter({'type':'result','usage':{'input_tokens':10,'cache_read_input_tokens':80,'cache_creation_input_tokens':5,'output_tokens':3}},'Claude Code');self.assertEqual(c['input_tokens'],95)
  c=counter({'event':'result','result':{'usageMetadata':{'promptTokenCount':100,'cachedContentTokenCount':90,'candidatesTokenCount':5}}},'Gemini');self.assertEqual(c['output_tokens'],5)
  self.assertIsNone(counter({'type':'turn.completed','usage':{'input_tokens':-1}},'Codex'));self.assertIsNone(counter({'type':'agent_message','usage':{'input_tokens':100}},'Codex'))
 def test_log_refresh_is_idempotent_and_includes_independent_review(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Desk(Path(tmp)/'home',Path(tmp)/'data');pid=d.mutate('project',{'name':'Test','company':'T'})['id'];tid=d.mutate('create',{'project_id':pid,'title':'Test','next_action':'test'})['id'];folder=d.data/'requests'/tid;folder.mkdir(parents=True);(folder/'receipt.json').write_text('{"engine":"Codex"}');log=folder/'cli.log'
   event={'type':'turn.completed','usage':{'input_tokens':100,'cached_input_tokens':70,'output_tokens':10}};log.write_text(json.dumps(event)+'\n');r=folder/'.review-1';r.mkdir();(r/'cli.log').write_text(json.dumps(event)+'\n')
   first=snapshot(d);second=snapshot(d);self.assertEqual(first['rows'],second['rows']);self.assertEqual(sum(x['input_tokens'] for x in first['rows']),200)
   log.write_text(json.dumps(event)+'\n'+json.dumps(event)+'\n');self.assertEqual(sum(x['input_tokens'] for x in snapshot(d)['rows']),300)

class ProgressTests(unittest.TestCase):
 def test_ai_failures_are_not_human_actions(self):
  for status in ('issues','unverified'):
   r=classify({'execution_status':'succeeded','review':{'status':status,'summary':'Needs work'}});self.assertEqual(r['owner'],'AI');self.assertEqual(r['status'],'保留')
 def test_verified_output_and_deploy_decision_are_distinct(self):
  receipt={'execution_status':'succeeded','review':{'status':'reviewed'}};self.assertEqual(classify(receipt)['status'],'完了')
  receipt['workspace']={'changed_files':['main.py']};self.assertEqual(classify(receipt)['owner'],'今川さん');self.assertEqual(classify(receipt,growth_state='superseded')['label'],'次の改善へ引継ぎ済み')

class DeltaTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.desk=Desk(self.root/'home',self.root/'data');self.pid=self.desk.mutate('project',{'name':'Test','company':'T'})['id'];self.calls=[]
 def folder(self,text='original',report='one',rule='rule1'):
  tid=self.desk.mutate('create',{'project_id':self.pid,'title':'Test','next_action':'test'})['id'];folder=self.desk.data/'requests'/tid;(folder/'workspace').mkdir(parents=True);(folder/'workspace/main.py').write_text(text);(folder/'report.txt').write_text(report);(folder/'response.txt').write_text(report);(folder/'project_context.json').write_text(json.dumps({'reference_bundle':{'documents':[{'kind':'rules','full_sha256':rule}]}}));return folder
 def review(self,folder):
  files=[{'name':'workspace/main.py'},{'name':'report.txt'}];evidence={'status':'passed','manifest':{'main.py':hashlib.sha256((folder/'workspace/main.py').read_bytes()).hexdigest()}};job={'kind':'implementation','registered_workspace':True,'isolated_test_evidence':evidence,'_reference_hashes':[(d['kind'],d['full_sha256']) for d in json.loads((folder/'project_context.json').read_text())['reference_bundle']['documents']]}
  def reviewer(folder,prompt,job,engines,env,files):
   names=[f['name'] for f in files]+['response.txt'];self.calls.append(names);return {'status':'reviewed','independent':True,'summary':'checked','checks':[{'file':n,'kind':'code','observation':'independent check'} for n in names]}
  return review_run(folder,'same requirements',job,[],{},files,reviewer)
 def test_report_only_change_reuses_code_but_code_or_rules_changes_invalidate(self):
  self.review(self.folder());result=self.review(self.folder(report='new report'));self.assertEqual(result['reused_checks'],1);self.assertNotIn('workspace/main.py',self.calls[-1]);self.assertEqual(result['status'],'reviewed')
  self.assertEqual(self.review(self.folder(text='changed'))['reused_checks'],0);self.assertEqual(self.review(self.folder(rule='rule2'))['reused_checks'],0)

class ProgramTests(unittest.TestCase):
 def test_csv_missing_invalid_and_duplicates_are_not_silently_zero(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'data.csv';path.write_text('id,amount\na,10.1\na,2.2\nb,\nc,NaN\n');result=load('test_csv','table-audit/audit.py').audit(path,'id','amount');self.assertEqual(result['sum_of_valid_values'],'12.3');self.assertFalse(result['sum_complete']);self.assertEqual(len(result['duplicate_rows']),1);self.assertEqual(result['invalid_amounts'],[5])
 def test_attachment_checks_are_read_only_and_skip_links(self):
  with tempfile.TemporaryDirectory() as tmp:
   folder=Path(tmp);(folder/'a.csv').write_text('id\n1\n');(folder/'same.csv').write_text('id\n1\n');(folder/'escape').symlink_to('/etc/passwd');before=(folder/'a.csv').read_bytes();r=inspect(folder);self.assertEqual(r['inventory']['total_files'],2);self.assertEqual(len(r['inventory']['duplicates']),1);self.assertEqual(r['csv_checks'][0]['result']['rows'],1);self.assertEqual((folder/'a.csv').read_bytes(),before)

class TaskContextTests(unittest.TestCase):
 def test_task_details_are_preserved_but_not_repeated_in_initial_index(self):
  from project_context import prompt_view
  context={'tasks':[{'id':'one','title':'Task','status':'保留','result':'long result'*2000,'blocker':'reason'}]}
  view=prompt_view(context,'Codex');self.assertNotIn('result',view['tasks'][0]);self.assertEqual(view['task_details']['path'],'project_context.json');self.assertEqual(prompt_view(context,'Gemini')['tasks'][0]['result'],context['tasks'][0]['result']);self.assertIn('result',context['tasks'][0])
