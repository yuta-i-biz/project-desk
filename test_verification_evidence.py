import json,tempfile,unittest
from pathlib import Path
from verification_evidence import runner,successful_tests
class EvidenceTests(unittest.TestCase):
 def test_real_runner_shapes(self):
  for command in ['cd workspace && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover','/bin/zsh -lc "cd workspace && python3 -m unittest discover"']:
   self.assertEqual(runner(command),'unittest')
  self.assertEqual(runner('npm test'),'npm test')
 def test_echo_and_masked_failure_are_not_proof(self):
  self.assertIsNone(runner('echo "python3 -m unittest"'));self.assertIsNone(runner('python3 -m unittest || true'))
 def test_only_successful_tool_events_not_model_prose(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'log'
   events=[{'type':'item.completed','item':{'type':'agent_message','text':'テスト済み'}},{'type':'item.completed','item':{'type':'command_execution','command':'python3 -m unittest','exit_code':1}},{'type':'item.completed','item':{'type':'command_execution','command':'python3 -m unittest','exit_code':0,'aggregated_output':'Ran 1 test\nOK'}}]
   path.write_text('\n'.join(json.dumps(e) for e in events));r=successful_tests(path);self.assertEqual(len(r),1);self.assertEqual(r[0]['runner'],'unittest');self.assertEqual(len(r[0]['command_sha256']),64)
