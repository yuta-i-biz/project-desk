import json,tempfile,unittest,threading
from pathlib import Path
from app import Desk
from workflows import create,approve,plans,tick,recover
class WorkflowTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();root=Path(self.tmp.name);self.d=Desk(root/'home',root/'data');self.pid=self.d.mutate('project',{'name':'Fixture','company':'Test'})['id'];self.calls=[]
 def tearDown(self):self.tmp.cleanup()
 def plan(self):return create(self.d,{'project_id':self.pid,'steps':[{'kind':'draft','prompt':'案を作る','criteria':'案が2つある'},{'kind':'analysis','prompt':'比較する','criteria':'違いが明記される'}]})['id']
 def submit(self,d,payload):
  self.calls.append(payload);tid=d.mutate('create',{'project_id':self.pid,'title':'Fixture step','next_action':'Fixture run'})['id'];(d.data/'requests'/tid).mkdir(parents=True);return {'task_id':tid}
 def test_draft_never_starts_without_explicit_approval(self):
  ident=self.plan();tick(self.d,self.submit);self.assertFalse(self.calls)
  with self.assertRaises(ValueError):approve(self.d,{'id':ident,'confirmed':False})
 def test_next_step_requires_independent_pass(self):
  ident=self.plan();approve(self.d,{'id':ident,'confirmed':True});tick(self.d,self.submit);tick(self.d,self.submit);self.assertEqual(len(self.calls),1)
  folder=self.d.data/'requests'/plans(self.d)[0]['steps'][0]['task_id'];(folder/'receipt.json').write_text(json.dumps({'execution_status':'succeeded','review':{'status':'reviewed'}}));tick(self.d,self.submit);tick(self.d,self.submit);self.assertEqual(len(self.calls),2);self.assertTrue(self.calls[1]['_autonomous'])
 def test_unverified_holds_and_never_retries(self):
  ident=self.plan();approve(self.d,{'id':ident,'confirmed':True});tick(self.d,self.submit);(self.d.data/'requests'/plans(self.d)[0]['steps'][0]['task_id']/'receipt.json').write_text(json.dumps({'execution_status':'succeeded','review':{'status':'unverified'}}));tick(self.d,self.submit);tick(self.d,self.submit);self.assertEqual(len(self.calls),1);self.assertEqual(plans(self.d)[0]['state'],'held')
 def test_uncertain_dispatch_after_crash_never_replays(self):
  ident=self.plan();approve(self.d,{'id':ident,'confirmed':True})
  with self.d.connect() as c:c.execute("UPDATE work_steps SET state='dispatching' WHERE position=0")
  recover(self.d);tick(self.d,self.submit);self.assertFalse(self.calls);self.assertEqual(plans(self.d)[0]['state'],'held')
 def test_competing_ticks_dispatch_once(self):
  ident=self.plan();approve(self.d,{'id':ident,'confirmed':True});threads=[threading.Thread(target=tick,args=(self.d,self.submit)) for _ in range(2)]
  for t in threads:t.start()
  for t in threads:t.join()
  self.assertEqual(len(self.calls),1)
 def test_external_actions_and_missing_conditions_rejected(self):
  for step in [{'kind':'send','prompt':'x','criteria':'x'},{'kind':'draft','prompt':'送信して','criteria':'x'},{'kind':'draft','prompt':'案を作る','criteria':''}]:
   with self.assertRaises(ValueError):create(self.d,{'project_id':self.pid,'steps':[step]})
 def test_workflow_http_routes_require_enabled_execution_and_origin(self):
  import urllib.request,urllib.error
  from http.server import ThreadingHTTPServer
  from app import Handler
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.desk=self.d;thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port)
  body=json.dumps({'project_id':self.pid,'steps':[{'kind':'analysis','prompt':'比較する','criteria':'違いを示す'}]}).encode()
  def post(route,data=body,origin_value=origin):return urllib.request.Request(origin+route,data=data,headers={'Origin':origin_value,'X-Desk-Token':self.d.token,'Content-Type':'application/json'})
  try:
   with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(post('/api/workflows/create'))
   self.assertEqual(error.exception.code,503)
   (self.d.data/'node.json').write_text('{"enable_user_requests":true}')
   with urllib.request.urlopen(post('/api/workflows/create')) as response:r=json.load(response)
   self.assertEqual(r['state'],'draft')
   with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(post('/api/workflows/approve',json.dumps({'id':r['id'],'confirmed':False}).encode()))
   self.assertEqual(error.exception.code,400)
   with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(post('/api/workflows/approve',json.dumps({'id':r['id'],'confirmed':True}).encode(),origin_value='https://other.test'))
   self.assertEqual(error.exception.code,403)
   self.assertEqual(plans(self.d)[0]['state'],'draft')
   with urllib.request.urlopen(post('/api/workflows/approve',json.dumps({'id':r['id'],'confirmed':True}).encode())) as response:self.assertEqual(response.status,200)
   self.assertEqual(plans(self.d)[0]['state'],'active')
  finally:server.shutdown();server.server_close();thread.join()
