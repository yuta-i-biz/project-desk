import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from project_context import bundle,MAX_FILE,redact
class ContextTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.home=Path(self.tmp.name);self.ledger=self.home/'.claude/runtime/ledger';self.ledger.mkdir(parents=True);self.folder=self.home/'request';self.folder.mkdir();self.desk=SimpleNamespace(home=self.home,machine='このMac')
 def tearDown(self):self.tmp.cleanup()
 def source(self,path,machine='このMac'):return {'sources':[{'type':'案件台帳','path':str(path),'machine':machine}]}
 def test_selected_project_only_and_fresh_content(self):
  p=self.ledger/'one.md';p.write_text('current');(self.ledger/'two.md').write_text('other project');r=bundle(self.desk,self.source(p),self.folder);self.assertEqual(len(r['documents']),1);self.assertEqual(r['documents'][0]['text'],'current');p.write_text('new state');self.assertEqual(bundle(self.desk,self.source(p),self.folder)['documents'][0]['text'],'new state')
 def test_other_machine_never_uses_same_local_path(self):
  p=self.ledger/'one.md';p.write_text('local');self.assertFalse(bundle(self.desk,self.source(p,'Mac mini'),self.folder)['documents'])
 def test_outside_path_symlink_and_traversal_rejected(self):
  p=self.home/'secret.md';p.write_text('not allowed');link=self.ledger/'link.md';link.symlink_to(p)
  for path in (p,link,self.ledger/'../secret.md'):self.assertFalse(bundle(self.desk,self.source(path),self.folder)['documents'])
 def test_truncation_is_explicit(self):
  p=self.ledger/'long.md';p.write_text('x'*(MAX_FILE+100));r=bundle(self.desk,self.source(p),self.folder)['documents'][0];self.assertTrue(r['truncated']);self.assertEqual(len(r['text']),MAX_FILE)
 def test_registered_rules_and_policy_are_embedded(self):
  w=self.folder/'workspace';w.mkdir();(w/'AGENTS.md').write_text('project rule');p=self.home/'.claude/runtime/auto_run_criteria.md';p.write_text('policy');r=bundle(self.desk,{},self.folder);self.assertEqual([d['kind'] for d in r['documents']],['execution_policy','registered_project_rules'])
 def test_registered_rules_for_text_only_request(self):
  import json,subprocess
  source=self.home/'code';source.mkdir();(source/'CLAUDE.md').write_text('project-only rule');subprocess.run(['git','init','-q',str(source)],check=True)
  data=self.home/'data';data.mkdir();(data/'workspace_sources.json').write_text(json.dumps({'p':{'source':str(source),'mode':'copy','registered_locally':True}}));self.desk.data=data
  r=bundle(self.desk,{'id':'p'},self.folder);self.assertEqual(r['documents'][0]['text'],'project-only rule')
 def test_common_and_gemini_rules_and_version(self):
  common=self.home/'.claude/CLAUDE.md';common.parent.mkdir(exist_ok=True);common.write_text('same common rules')
  w=self.folder/'workspace';w.mkdir();(w/'GEMINI.md').write_text('Gemini project rule')
  first=bundle(self.desk,{},self.folder);self.assertEqual([d['kind'] for d in first['documents']],['common_rules','registered_project_rules'])
  self.assertEqual(first['rules_fingerprint'],bundle(self.desk,{},self.folder)['rules_fingerprint'])
  common.write_text('updated common rules');self.assertNotEqual(first['rules_fingerprint'],bundle(self.desk,{},self.folder)['rules_fingerprint'])
 def test_fixed_common_root_may_be_synced_but_leaf_links_still_rejected(self):
  import shutil
  old=self.home/'.claude';sync=self.home/'sync';shutil.move(str(old),str(sync));old.symlink_to(sync,target_is_directory=True)
  (sync/'CLAUDE.md').write_text('synced common rules');r=bundle(self.desk,{},self.folder);self.assertIn('synced common rules',[d['text'] for d in r['documents']])
  (sync/'CLAUDE.md').unlink();secret=self.home/'private.md';secret.write_text('must not transmit');(sync/'CLAUDE.md').symlink_to(secret)
  self.assertNotIn('must not transmit',[d['text'] for d in bundle(self.desk,{},self.folder)['documents']])
 def test_secret_patterns_removed(self):
  text='api_key: fake-value\npassword = fake-password\n-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\nordinary text';safe=redact(text);self.assertNotIn('fake',safe);self.assertIn('ordinary text',safe)

class ProviderContextTests(unittest.TestCase):
 def test_each_provider_receives_selected_project_text(self):
  import json,subprocess
  from unittest.mock import patch
  from app import Desk
  import execution
  for engine in ('Codex','Claude Code','Gemini'):
   with self.subTest(engine=engine),tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);home=root/'home';ledger=home/'.claude/runtime/ledger/Test';ledger.mkdir(parents=True)
    (home/'.claude/CLAUDE.md').write_text('SHARED_POLICY_REFERENCE')
    (ledger/'sample.md').write_text('## 目的\nSELECTED_PROJECT_REFERENCE\n## 次アクション\n比較する\n')
    d=Desk(home,root/'data');pid=d.snapshot()['projects'][0]['id'];(d.data/'engines.json').write_text(json.dumps([{'engine':engine,'available':True}]))
    inputs=[]
    def runner(command,**kw):
     if command[1:3]==['login','status']:return subprocess.CompletedProcess(command,0,'ChatGPT','')
     inputs.append(kw['input']);(kw['cwd']/'response.txt').write_text('検証用の回答');return subprocess.CompletedProcess(command,0)
    with patch.object(execution.POOL,'submit',side_effect=lambda fn,**kw:fn()),patch.object(execution.subprocess,'run',side_effect=runner),patch('auth_status.claude_probe',return_value={'available':True}),patch('gemini_adapter.command',return_value=['mock-gemini']),patch('gemini_adapter.response',return_value='検証用の回答'):
     result=execution.submit(d,{'project_id':pid,'engine':engine,'prompt':'案件資料を要約してください'})
    self.assertEqual(len(inputs),1);self.assertIn('SELECTED_PROJECT_REFERENCE',inputs[0]);self.assertIn('SHARED_POLICY_REFERENCE',inputs[0]);self.assertIn('truncated',inputs[0]);context=json.loads((d.data/'requests'/result['task_id']/'project_context.json').read_text());self.assertIn('project_ledger',[d['kind'] for d in context['reference_bundle']['documents']]);self.assertEqual(len(context['reference_bundle']['rules_fingerprint']),64)
