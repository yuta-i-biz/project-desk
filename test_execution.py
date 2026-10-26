import json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app import Desk
import execution
from runtime_profile import describe
class ExecutionQualityTests(unittest.TestCase):
 def test_config_names_exclude_secrets_and_do_not_claim_connected(self):
  with tempfile.TemporaryDirectory() as tmp:
   home=Path(tmp);(home/'.claude').mkdir();(home/'.claude.json').write_text(json.dumps({'mcpServers':{'sample':{'env':{'TOKEN':'secret-value'}}}}));(home/'.claude/settings.json').write_text(json.dumps({'hooks':{'Stop':[]},'enabledPlugins':{'enabled':True,'disabled':False}}))
   r=describe(home,'Claude Code');self.assertNotIn('secret-value',json.dumps(r));self.assertEqual(r['configured_claude_environment']['mcp_servers'],['sample']);self.assertEqual(r['configured_claude_environment']['plugins'],['enabled']);self.assertEqual(r['parity'],'limited')
 def test_cli_failure_is_paused_and_not_sent_for_review(self):self.execute(returncode=1)
 def test_long_answer_and_unverified_review_are_preserved(self):self.execute(returncode=0)
 def execute(self,returncode):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);d=Desk(root/'home',root/'data');(d.data/'engines.json').write_text('[{"engine":"Codex","available":true}]');pid=d.mutate('project',{'name':'Test','company':'Test'})['id']
   def runner(command,**kw):
    if command[1:3]==['login','status']:return subprocess.CompletedProcess(command,0,'ChatGPT','')
    (kw['cwd']/'response.txt').write_text('回答'*4000)
    return subprocess.CompletedProcess(command,returncode)
   with patch.object(execution.POOL,'submit',side_effect=lambda fn,**kw:fn()),patch.object(execution.subprocess,'run',side_effect=runner),patch('review.run',return_value={'status':'unverified','summary':'目視検証が未確認','checks':[],'independent':False}) as review:
    r=execution.submit(d,{'project_id':pid,'prompt':'画像を作成して'})
   t=next(t for t in d.snapshot()['tasks'] if t['id']==r['task_id']);receipt=json.loads((d.data/'requests'/t['id']/'receipt.json').read_text())
   self.assertEqual(t['status'],'保留' if returncode else '確認待ち');self.assertFalse(receipt['independent_verification']);self.assertEqual(len(receipt['summary']),8000)
   self.assertEqual(receipt['execution_status'],'failed' if returncode else 'succeeded')
   if returncode:review.assert_not_called()
   else:review.assert_called_once();self.assertEqual(t['blocker'],'目視検証が未確認')
 def test_queued_request_loads_history_when_started(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);d=Desk(root/'home',root/'data');(d.data/'engines.json').write_text('[{"engine":"Codex","available":true}]');pid=d.mutate('project',{'name':'Test','company':'Test'})['id'];jobs=[]
   with patch.object(execution.POOL,'submit',side_effect=lambda fn,**kw:jobs.append(fn)):
    first=execution.submit(d,{'project_id':pid,'prompt':'最初の相談'});second=execution.submit(d,{'project_id':pid,'prompt':'続きの相談'})
   (d.data/'requests'/first['task_id']/'receipt.json').write_text(json.dumps({'request':'最初の相談','summary':'後から完成した返答'}))
   def runner(command,**kw):
    if command[1:3]==['login','status']:return subprocess.CompletedProcess(command,0,'ChatGPT','')
    self.assertIn('後から完成した返答',kw['input']);(kw['cwd']/'response.txt').write_text('続き');return subprocess.CompletedProcess(command,0)
   with patch.object(execution.subprocess,'run',side_effect=runner):jobs[1]()
   receipt=json.loads((d.data/'requests'/second['task_id']/'receipt.json').read_text());self.assertEqual(receipt['context']['previous_task_ids'],[first['task_id']])
