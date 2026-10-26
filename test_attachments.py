import unittest,tempfile,json,zipfile
from pathlib import Path
from unittest.mock import patch
from app import Desk
from attachments import receive,records,context,classify,text_of,store_drive
class AttachmentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);self.d=Desk(root/'home',root/'data');self.a=self.d.mutate('project',{'name':'採用管理','company':'会社A'})['id'];self.b=self.d.mutate('project',{'name':'販売管理','company':'会社B'})['id']
 def tearDown(self):self.tmp.cleanup()
 def upload(self,name,data,pid=''):
  with patch('attachments.POOL.submit'):return receive(self.d,name,data,pid)
 def test_text_and_reserved_names_preserve_original(self):
  r=self.upload('../record.json',b'{"hello":"world"}',self.a);folder=self.d.data/'uploads'/r['id'];self.assertEqual((folder/'original'/'record.json').read_bytes(),b'{"hello":"world"}');self.assertEqual(json.loads((folder/'record.json').read_text())['project_id'],self.a);self.assertEqual(context(self.d,[r['id']],self.a)[0]['text'],'{"hello":"world"}')
 def test_classification_and_ambiguity(self):
  projects=self.d.collect()['projects'];self.assertEqual(classify(projects,'採用管理.txt','')['id'],self.a);self.assertIsNone(classify(projects,'unknown.bin',''));self.assertIsNone(classify(projects,'採用管理と販売管理.txt',''))
 def test_cross_project_rejected(self):
  r=self.upload('a.txt',b'text',self.a)
  with self.assertRaises(ValueError):context(self.d,[r['id']],self.b)
  self.assertEqual(len(context(self.d,[r['id']],self.b,True)),1)
 def test_binary_and_drive_failure_keep_file(self):
  r=self.upload('movie.bin',b'\x00\x01\xff',self.a);self.assertIn('未対応',r['read_status'])
  with patch('drive_store.store',side_effect=RuntimeError('no connection')):store_drive(self.d,r['id'])
  self.assertIn('要確認',records(self.d)[0]['drive_status']);self.assertEqual((self.d.data/'uploads'/r['id']/'original'/'movie.bin').read_bytes(),b'\x00\x01\xff')
 def test_xlsx_shared_strings(self):
  path=Path(self.tmp.name)/'test.xlsx'
  with zipfile.ZipFile(path,'w') as z:
   z.writestr('xl/sharedStrings.xml','<sst xmlns="x"><si><t>売上</t></si></sst>');z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="x"><sheetData><row><c r="A1" t="s"><v>0</v></c><c r="B1"><v>123</v></c></row></sheetData></worksheet>')
  text,status=text_of(path);self.assertIn('A1=売上',text);self.assertIn('B1=123',text)
 def test_empty_invalid_project_and_id(self):
  with self.assertRaises(ValueError):self.upload('a.txt',b'')
  with self.assertRaises(ValueError):self.upload('a.txt',b'text','invalid')
  with self.assertRaises(ValueError):context(self.d,['../../secret'],self.a)
 def test_company_override_keeps_project_id(self):
  pid=self.d.mutate('project',{'company':'会社子','name':'案件'})['id'];(self.d.data/'company_overrides.json').write_text(json.dumps({'会社子':'会社親'}));self.d.invalidate();p=next(p for p in self.d.collect()['projects'] if p['id']==pid);self.assertEqual(p['company'],'会社親');self.assertIn('会社子',p['name'])
 def test_http_upload_authentication_and_origin(self):
  import threading,urllib.request,urllib.error
  from http.server import ThreadingHTTPServer
  from app import Handler
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.desk=self.d;server.remote_access=True
  thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port)
  headers={'Origin':origin,'X-Desk-Token':self.d.token,'X-File-Name':'test.txt','Content-Type':'application/octet-stream'}
  try:
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(urllib.request.Request(origin+'/api/files/upload',data=b'test',headers=headers))
   self.assertEqual(e.exception.code,401);headers['Cookie']='desk_session='+self.d.access['session'];headers['Origin']='https://wrong.example'
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(urllib.request.Request(origin+'/api/files/upload',data=b'test',headers=headers))
   self.assertEqual(e.exception.code,403);headers['Origin']=origin
   with patch('attachments.POOL.submit'):
    with urllib.request.urlopen(urllib.request.Request(origin+'/api/files/upload?project_id='+self.a,data=b'test',headers=headers)) as response:r=json.load(response)
   self.assertEqual(r['project_id'],self.a);self.assertEqual(r['read_status'],'読取済み')
  finally:server.shutdown();server.server_close();thread.join()
