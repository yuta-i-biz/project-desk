import json,tempfile,time,unittest
from pathlib import Path
from claude_bridge import atomic,status,folder_for,process_job
class BridgeTests(unittest.TestCase):
 def test_status_expires_and_never_exports_identity(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);atomic(p/'claude_gui_status.json',{'checked_at':time.time(),'state':'connected','email':'secret'});self.assertTrue(status(p)['available']);self.assertNotIn('secret',json.dumps(status(p)));atomic(p/'claude_gui_status.json',{'checked_at':0,'state':'connected'});self.assertIsNone(status(p))
 def test_arbitrary_working_directory_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   for tid in ('../outside','task-123','/tmp/file'):
    with self.assertRaises(ValueError):folder_for(Path(tmp),tid)
 def test_only_fixed_claude_command_and_no_replay(self):
  with tempfile.TemporaryDirectory() as tmp:
   data=Path(tmp);tid='task-'+'a'*16;folder=data/'requests'/tid;folder.mkdir(parents=True);job=data/'job.json';atomic(job,{'task_id':tid,'created':time.time(),'state':'queued','prompt':'fixture','command':['unsafe']});calls=[]
   def run(cmd,**kw):calls.append(cmd);return type('Result',(),{'returncode':0})()
   process_job(data,job,run);process_job(data,job,run);self.assertEqual(len(calls),1);self.assertNotIn('unsafe',str(calls));self.assertNotIn('prompt',json.loads(job.read_text()));self.assertEqual(json.loads(job.read_text())['state'],'done')
 def test_execution_copy_does_not_overwrite_protected_metadata(self):
  from claude_bridge import copy_request
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);a=root/'source';b=root/'target';a.mkdir();b.mkdir();(a/'project_context.json').write_text('changed');(b/'project_context.json').write_text('original');(a/'answer.txt').write_text('result')
   copy_request(a,b,collect=True);self.assertEqual((b/'project_context.json').read_text(),'original');self.assertEqual((b/'answer.txt').read_text(),'result')
 def test_execution_copy_rejects_symlinks(self):
  from claude_bridge import copy_request
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);a=root/'a';b=root/'b';a.mkdir();b.mkdir();(a/'link').symlink_to(root/'outside')
   with self.assertRaises(ValueError):copy_request(a,b)
