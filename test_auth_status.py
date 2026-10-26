import json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from auth_status import claude_probe
class ClaudeProbeTests(unittest.TestCase):
 def test_connected_does_not_export_identity(self):
  r=subprocess.CompletedProcess([],0,json.dumps({'loggedIn':True,'authMethod':'claude.ai','email':'private@example.test'}),'')
  with patch('auth_status.subprocess.run',return_value=r):p=claude_probe(Path('/home/test'),{})
  self.assertTrue(p['available']);self.assertNotIn('private@example',json.dumps(p))
 def test_background_keychain_failure_is_unknown_not_logout(self):
  with tempfile.TemporaryDirectory() as tmp:
   home=Path(tmp);k=home/'Library/Keychains/login.keychain-db';k.parent.mkdir(parents=True);k.touch()
   results=[subprocess.CompletedProcess([],0,'{"loggedIn":false,"authMethod":"none"}',''),subprocess.CompletedProcess([],1,'','User interaction is not allowed')]
   with patch('auth_status.subprocess.run',side_effect=results):p=claude_probe(home,{})
   self.assertFalse(p['available']);self.assertEqual(p['state'],'credential_unavailable');self.assertIn('未確認',p['detail'])
 def test_missing_or_malformed_cli_is_not_a_claim_of_logout(self):
  for value in [OSError('missing'),subprocess.CompletedProcess([],1,'not-json','')]:
   with patch('auth_status.subprocess.run',side_effect=value if isinstance(value,Exception) else None,return_value=value):
    self.assertEqual(claude_probe(Path('/home/test'),{})['state'],'not_verified')
