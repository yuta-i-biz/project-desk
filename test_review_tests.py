import subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import review_tests
class IsolatedTests(unittest.TestCase):
 def test_missing_workspace(self):
  self.assertEqual(review_tests.run(Path('/nonexistent-desk-code'))['status'],'unverified')
 def test_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'escape').symlink_to('/etc/passwd')
   with patch('review_tests.Path.is_file',return_value=True):self.assertEqual(review_tests.run(p)['status'],'unverified')
 def test_zero_tests_not_pass(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test_empty.py').write_text('')
   with patch('review_tests.Path.is_file',return_value=True),patch('review_tests.subprocess.run',return_value=subprocess.CompletedProcess([],0,'Ran 0 tests\nOK','')):self.assertEqual(review_tests.run(p)['status'],'unverified')
 def test_restrictions_and_environment(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'test_sample.py').write_text('fixture')
   def process(command,**kw):
    for rule in ['(deny network*)','(deny file-write*)','(subpath "/Users")']:self.assertIn(rule,command[2])
    self.assertNotIn('ANTHROPIC_API_KEY',kw['env']);self.assertNotEqual(kw['cwd'],p)
    return subprocess.CompletedProcess(command,0,'Ran 1 test\nOK','')
   with patch('review_tests.Path.is_file',return_value=True),patch('review_tests.subprocess.run',side_effect=process):r=review_tests.run(p)
   self.assertEqual(r['status'],'passed');self.assertIn('test_sample.py',r['manifest'])
