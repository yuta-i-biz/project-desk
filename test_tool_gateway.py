import json,tempfile,unittest
from pathlib import Path
from tool_gateway import Gateway,codex_config,file_ids
class Fake:
 def __init__(self):self.calls=[]
 def call(self,method,params=None):
  self.calls.append((method,params))
  return {'tools':[{'name':n,'inputSchema':{}} for n in ['docs_get','sheets_read','create_file','sheets_values_update','read_file_content']]} if method=='tools/list' else {'content':[]}
class GatewayTests(unittest.TestCase):
 def test_tools_hide_writes(self):
  f=Fake();g=Gateway(f,['allowed-file-id']);self.assertEqual({t['name'] for t in g.handle('tools/list',{})['tools']},{'docs_get','sheets_read','read_file_content'})
 def test_wrong_file_and_write_never_forward(self):
  f=Fake();g=Gateway(f,['allowed-file-id'])
  for name,args in [('docs_get',{'document_id':'other-file-id'}),('create_file',{'file_id':'allowed-file-id'})]:
   with self.assertRaises(ValueError):g.handle('tools/call',{'name':name,'arguments':args})
  self.assertFalse(f.calls)
 def test_allowed_read_and_fixed_metadata(self):
  f=Fake();g=Gateway(f,['allowed-file-id']);g.handle('tools/call',{'name':'get_file_metadata','arguments':{'file_id':'allowed-file-id','fields':'permissions'}});self.assertNotIn('permissions',f.calls[0][1]['arguments']['fields'])
 def test_only_google_urls_in_explicit_request(self):
  self.assertEqual(file_ids('https://docs.google.com/document/d/selected-file-id/edit https://evil.test/document/d/other-file-id'),['selected-file-id'])
 def test_config_never_embeds_credential_values(self):
  with tempfile.TemporaryDirectory() as tmp:
   h=Path(tmp);(h/'.claude.json').write_text(json.dumps({'mcpServers':{'google-services':{'command':'python','env':{'TOKEN':'private-secret'}}}}));folder=h/'request';folder.mkdir();args=codex_config(h,folder,'https://docs.google.com/document/d/selected-file-id/edit');self.assertTrue(args);self.assertNotIn('private-secret',str(args));self.assertEqual(json.loads((folder/'tool_scope.json').read_text())['file_ids'],['selected-file-id'])
 def test_autonomy_disables_existing_tool_servers(self):
  import subprocess
  from unittest.mock import patch
  from tool_gateway import disabled_mcp_config
  with patch('tool_gateway.subprocess.run',side_effect=[subprocess.CompletedProcess([],0,'[{"name":"codex_app"},{"name":"cua_repl"}]',''),subprocess.CompletedProcess([],0,'[{"name":"codex_app","enabled":false},{"name":"cua_repl","enabled":false}]','')]):flags=disabled_mcp_config('codex',{})
  self.assertIn('mcp_servers.codex_app.enabled=false',flags);self.assertIn('mcp_servers.cua_repl.enabled=false',flags)
 def test_unreadable_tool_configuration_stops_autonomy(self):
  import subprocess
  from unittest.mock import patch
  from tool_gateway import disabled_mcp_config
  with patch('tool_gateway.subprocess.run',return_value=subprocess.CompletedProcess([],1,'','')):
   with self.assertRaises(RuntimeError):disabled_mcp_config('codex',{})
