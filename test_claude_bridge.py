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
