import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from workspace import prepare,register,report
class WorkspaceTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.home=Path(self.temp.name);self.source=self.home/'project';self.source.mkdir();self.data=self.home/'data';self.data.mkdir();self.folder=self.data/'requests/test';self.folder.mkdir(parents=True)
  subprocess.run(['git','init','-q',str(self.source)],check=True,capture_output=True)
  import sqlite3
  with sqlite3.connect(self.data/'desk.sqlite3') as c:c.execute('CREATE TABLE projects(id TEXT PRIMARY KEY)');c.execute('INSERT INTO projects VALUES(?)',('p',))
  self.desk=SimpleNamespace(home=self.home,data=self.data)
 def tearDown(self):self.temp.cleanup()
 def add(self,name,content):
  p=self.source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content);return p
 def register(self):register(self.data,'p',self.source,self.home)
 def test_dirty_working_files_copy_tests_and_valid_patch(self):
  p=self.add('calc.py','print(1)\n');self.add('AGENTS.md','既存の案件ルール')
  subprocess.run(['git','-C',str(self.source),'add','.'],check=True);index_hash=hashlib.sha256((self.source/'.git/index').read_bytes()).hexdigest();p.write_text('print(2)')
  self.register();m=prepare(self.desk,'p',self.folder);self.assertEqual((self.folder/'workspace/calc.py').read_text(),'print(2)');self.assertTrue((self.folder/'workspace/AGENTS.md').exists())
  (self.folder/'workspace/calc.py').write_text('print(3)\n')
  result=subprocess.run([sys.executable,'calc.py'],cwd=self.folder/'workspace',capture_output=True,text=True,check=True);self.assertEqual(result.stdout,'3\n')
  r=report(m,self.folder);self.assertTrue(r['original_unchanged']);self.assertIn('calc.py',r['changed_files']);self.assertEqual(p.read_text(),'print(2)');self.assertEqual(hashlib.sha256((self.source/'.git/index').read_bytes()).hexdigest(),index_hash)
  subprocess.run(['git','-C',str(self.source),'apply','--check',str(self.folder/r['patch'])],check=True,capture_output=True)
 def test_tracked_secrets_and_external_symlinks_are_excluded(self):
  self.add('.env','secret');self.add('google_token.json','secret');self.add('.mcp.json','secret');self.add('main.py','print(1)');outside=self.home/'outside';outside.write_text('private');(self.source/'linked.py').symlink_to(outside)
  subprocess.run(['git','-C',str(self.source),'add','.'],check=True);self.register();m=prepare(self.desk,'p',self.folder)
  self.assertEqual(set(m['files']),{'main.py'});self.assertEqual(len(m['skipped']),4)
 def test_unregistered_and_unknown_project_do_not_copy(self):
  self.assertIsNone(prepare(self.desk,'p',self.folder))
  with self.assertRaises(ValueError):register(self.data,'other',self.source,self.home)
  self.assertFalse((self.folder/'workspace').exists())
 def test_source_changes_and_copy_symlinks_are_not_verified(self):
  p=self.add('main.py','original');self.register();m=prepare(self.desk,'p',self.folder);p.write_text('other-user-change');self.assertFalse(report(m,self.folder)['original_unchanged']);p.write_text('original');(self.folder/'workspace/new.py').symlink_to(self.home/'outside')
  with self.assertRaises(ValueError):report(m,self.folder)
 def test_size_bound_and_ignored_dependencies(self):
  self.add('main.py','a'*10);self.add('.gitignore','node_modules/\n');self.add('node_modules/lib.js','ignored');self.register()
  with patch('workspace.MAX_BYTES',1):
   with self.assertRaises(ValueError):prepare(self.desk,'p',self.folder)
  m=prepare(self.desk,'p',self.folder);self.assertFalse((self.folder/'workspace/node_modules').exists());self.assertTrue(report(m,self.folder)['original_unchanged'])
 def test_deletion_addition_and_no_newline_patch(self):
  self.add('remove.txt','remove');self.add('keep.txt','keep');self.register();m=prepare(self.desk,'p',self.folder);(self.folder/'workspace/remove.txt').unlink();(self.folder/'workspace/new.txt').write_text('new')
  r=report(m,self.folder);self.assertEqual(r['changed_files'],['new.txt','remove.txt']);subprocess.run(['git','-C',str(self.source),'apply','--check',str(self.folder/r['patch'])],check=True,capture_output=True)
