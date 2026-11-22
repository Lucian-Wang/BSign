import os
os.environ['RESEND_FROM']='BSign <noreply@example.test>'
import os,base64,secrets,tempfile,unittest,re
from unittest.mock import patch,Mock
os.environ['BSIGN_DATA']=tempfile.mkdtemp(prefix='bsign-registration-test-')
os.environ['BSIGN_MASTER_KEY']=base64.b64encode(secrets.token_bytes(32)).decode()
os.environ['BSIGN_ORIGIN']='http://testserver'
from fastapi.testclient import TestClient
from server.main import app,db,now
from server.mail_templates import verification_mail
class Registration(unittest.TestCase):
 def setUp(self):
  with db() as c:
   c.execute('DELETE FROM rate_limits');c.execute('DELETE FROM registration_codes');c.execute('DELETE FROM users')
  self.client=TestClient(app,headers={'Origin':'http://testserver'})
  self.payload={'email':'new@example.test','password':'A-strong-password-2026','language':'zh'}
 def clear_rate(self):
  with db() as c:c.execute('DELETE FROM rate_limits')
 def request_code(self,send):
  r=self.client.post('/api/registration-email',json=self.payload);self.assertEqual(r.status_code,200,r.text)
  return re.search(r'(?<!\d)\d{6}(?!\d)',send.call_args.kwargs['json']['text']).group()
 @patch.dict(os.environ,{'RESEND_API_KEY':'test-only'})
 @patch('server.main.httpx.post')
 def test_verify_before_create(self,send):
  send.return_value=Mock(raise_for_status=Mock())
  self.assertEqual(self.client.post('/api/register',json=self.payload).status_code,400)
  code=self.request_code(send)
  with db() as c:
   self.assertEqual(c.execute('SELECT COUNT(*) FROM users').fetchone()[0],0)
   self.assertNotEqual(c.execute('SELECT token FROM registration_codes').fetchone()[0],code)
  self.request_code(send);self.assertEqual(send.call_count,1)
  self.assertEqual(self.client.post('/api/register',json={**self.payload,'email':'other@example.test','code':code}).status_code,400)
  self.assertEqual(self.client.post('/api/register',json={**self.payload,'code':'xxxxxx'}).status_code,400)
  r=self.client.post('/api/register',json={**self.payload,'code':code});self.assertEqual(r.status_code,200,r.text)
  self.assertEqual(r.json()['user']['language'],'zh');self.assertIn('bsign_session',r.cookies)
  with db() as c:
   self.assertEqual(c.execute('SELECT COUNT(*) FROM registration_codes').fetchone()[0],0)
   self.assertEqual(c.execute('SELECT COUNT(*) FROM verified_emails').fetchone()[0],1)
  self.assertEqual(self.client.post('/api/register',json={**self.payload,'code':code}).status_code,400)
  self.clear_rate();self.client.post('/api/registration-email',json=self.payload);self.assertEqual(send.call_count,1)
 @patch.dict(os.environ,{'RESEND_API_KEY':'test-only'})
 @patch('server.main.httpx.post')
 def test_expiry_attempts_resend_failure(self,send):
  send.return_value=Mock(raise_for_status=Mock());code=self.request_code(send)
  with db() as c:c.execute('UPDATE registration_codes SET expires=?',(now()-1,))
  self.assertEqual(self.client.post('/api/register',json={**self.payload,'code':code}).status_code,400)
  with db() as c:c.execute('UPDATE registration_codes SET sent=?,expires=?',(now()-61,now()+600))
  new=self.request_code(send)
  for _ in range(5):
   self.clear_rate();self.assertEqual(self.client.post('/api/register',json={**self.payload,'code':'xxxxxx'}).status_code,400)
  self.clear_rate();self.assertEqual(self.client.post('/api/register',json={**self.payload,'code':new}).status_code,400)
  with db() as c:c.execute('UPDATE registration_codes SET sent=?',(now()-61,))
  send.side_effect=RuntimeError('provider failed')
  self.assertEqual(self.client.post('/api/registration-email',json=self.payload).status_code,502)
  with db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM registration_codes').fetchone()[0],0)
 def test_unconfigured_mail_closed_and_templates(self):
  with patch.dict(os.environ,{'RESEND_API_KEY':''}):self.assertEqual(self.client.post('/api/registration-email',json=self.payload).status_code,503)
  for lang in ['zh','en']:
   for purpose in ['register','recover']:
    content=verification_mail('123456',purpose,lang,'https://sign.example.test')
    self.assertIn('123456',content['text']);self.assertIn('https://sign.example.test',content['html']);self.assertIn('BSign',content['subject'])
if __name__=='__main__':unittest.main()
