import tempfile,unittest,threading,json,urllib.request,urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer
from app import Desk,Handler
from previews import describe
class PreviewTests(unittest.TestCase):
 def test_text_table_and_raw_types(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);p=root/'x.csv';p.write_text('名前,値\nA,2');r=describe(p,'/safe',root);self.assertEqual(r['kind'],'table');self.assertEqual(r['rows'][1],['A','2']);p=root/'x.txt';p.write_text('<script>bad()</script>');self.assertEqual(describe(p,'/safe',root)['kind'],'text');p=root/'x.html';p.write_text('<h1>report</h1>');self.assertEqual(describe(p,'/safe',root)['kind'],'html')
 def test_auth_path_and_html_sandbox(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);d=Desk(root/'home',root/'data');folder=d.data/'requests/task-abcdef';folder.mkdir(parents=True);(folder/'page.html').write_text('<script>fetch("https://example.com")</script><h1>Report</h1>');(folder/'receipt.json').write_text('{}');(folder/'.secret').write_text('private')
   server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.desk=d;server.remote_access=True;t=threading.Thread(target=server.serve_forever,daemon=True);t.start();origin='http://127.0.0.1:'+str(server.server_port);url=origin+'/api/artifact-preview?task_id=task-abcdef&file=page.html'
   try:
    with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(url)
    self.assertEqual(e.exception.code,401);headers={'Cookie':'desk_session='+d.access['session']}
    with urllib.request.urlopen(urllib.request.Request(url,headers=headers)) as response:self.assertEqual(json.load(response)['kind'],'html')
    with urllib.request.urlopen(urllib.request.Request(url+'&raw=1',headers=headers)) as response:self.assertIn('sandbox',response.headers['Content-Security-Policy']);self.assertIn("default-src 'none'",response.headers['Content-Security-Policy'])
    for name in ('receipt.json','.secret','../../access.json'):
     with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(urllib.request.Request(origin+'/api/artifact-preview?task_id=task-abcdef&file='+name,headers=headers))
     self.assertEqual(e.exception.code,404)
   finally:server.shutdown();server.server_close();t.join()
 def test_pdf_returns_image_pages(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);pdf=root/'file.pdf';pdf.write_bytes(b'%PDF fixture')
   with patch('previews.pdf_pages',return_value=(root,{'pages':['page-1.png','page-2.png'],'total':2})):
    data=describe(pdf,'/preview?raw=1',root)
   self.assertEqual(data['kind'],'pdf');self.assertEqual(data['pages'],['/preview?raw=1&page=1','/preview?raw=1&page=2'])
