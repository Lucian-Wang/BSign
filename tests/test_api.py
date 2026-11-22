import os
os.environ['RESEND_FROM']='BSign <noreply@example.test>'
from unittest.mock import patch, Mock
import re
import os,base64,tempfile,secrets,io,sqlite3,unittest
os.environ['BSIGN_DATA']=tempfile.mkdtemp(prefix='bsign-test-')
os.environ['BSIGN_MASTER_KEY']=base64.b64encode(secrets.token_bytes(32)).decode()
os.environ['BSIGN_ORIGIN']='http://testserver'
os.environ['BSIGN_BOOTSTRAP_TOKEN']=secrets.token_urlsafe(32)
os.environ.pop('RESEND_API_KEY',None)
from fastapi.testclient import TestClient
from PIL import Image
from server.main import app, db as database, now, DATA

class Isolation(unittest.TestCase):
    def test_full_security_flow(self):
        a=TestClient(app,headers={'Origin':'http://testserver'})
        b=TestClient(app,headers={'Origin':'http://testserver'})
        admin=TestClient(app,headers={'Origin':'http://testserver'})
        def register(client,email):
            with patch.dict(os.environ,{'RESEND_API_KEY':'test-key'}), patch('server.main.httpx.post') as send:
                send.return_value=Mock(raise_for_status=Mock())
                self.assertEqual(client.post('/api/registration-email',json={'email':email}).status_code,200)
                code=re.search(r'(?<!\d)([0-9]{6})(?!\d)',send.call_args.kwargs['json']['text']).group()
            r=client.post('/api/register',json={'email':email,'password':'Strong-test-password-2026','name':'Test user','code':code})
            self.assertEqual(r.status_code,200,r.text)
            q=r.json();client.headers['X-CSRF-Token']=q['csrf'];return q
        qa=register(a,'alice@example.test'); qb=register(b,'bob@example.test')
        self.assertEqual(a.patch('/api/preferences',json={'language':'zh'}).status_code,200)
        self.assertEqual(a.get('/api/me').json()['user']['language'],'zh')
        self.assertEqual(b.get('/api/me').json()['user']['language'],'en')
        self.assertEqual(a.patch('/api/preferences',json={'language':'fr'}).status_code,400)
        self.assertEqual(a.patch('/api/preferences',json={'language':'en'},headers={'X-CSRF-Token':'bad'}).status_code,403)
        company=a.post('/api/companies',json={'name':'Alice company'}).json()['id']
        self.assertEqual(b.get('/api/companies/'+company+'/stamps').status_code,404)
        self.assertEqual(b.delete('/api/companies/'+company).status_code,404)
        out=io.BytesIO();Image.new('RGBA',(80,80),(180,0,0,160)).save(out,'PNG');raw=out.getvalue()
        stamp={'name':'42 mm company seal','kind':'round','width':42,'height':42,'image':base64.b64encode(raw).decode()}
        r=a.post('/api/companies/'+company+'/stamps',json=stamp);self.assertEqual(r.status_code,200,r.text)
        sid=r.json()['id']
        self.assertEqual(a.get('/api/stamps/'+sid+'/image').status_code,200)
        self.assertEqual(b.get('/api/stamps/'+sid+'/image').status_code,404)
        self.assertEqual(b.patch('/api/stamps/'+sid,json=stamp).status_code,404)
        with sqlite3.connect(DATA/'bsign.db') as db:
            cipher,nonce=db.execute('SELECT cipher,nonce FROM stamps WHERE id=?',(sid,)).fetchone()
            self.assertNotIn(b'PNG',cipher);self.assertNotEqual(cipher,raw);self.assertEqual(len(nonce),12)
        self.assertEqual(a.post('/api/companies',json={'name':'Forged'},headers={'Origin':'https://evil.test'}).status_code,403)
        self.assertEqual(a.post('/api/companies',json={'name':'Forged'},headers={'X-CSRF-Token':'invalid'}).status_code,403)
        wrong={**stamp,'image':base64.b64encode(b'%PDF-1.7 document').decode()}
        self.assertEqual(a.post('/api/companies/'+company+'/stamps',json=wrong).status_code,400)
        self.assertEqual(a.post('/api/pdf',json={}).status_code,404)
        r=admin.post('/api/bootstrap',json={'email':'ignored@test.com','password':'Admin-test-password-2026','name':'Admin','token':os.environ['BSIGN_BOOTSTRAP_TOKEN']})
        self.assertEqual(r.status_code,200,r.text);admin.headers['X-CSRF-Token']=r.json()['csrf']
        self.assertEqual(admin.get('/api/companies').status_code,403)
        self.assertEqual(admin.get('/api/stamps/'+sid+'/image').status_code,403)
        self.assertEqual(a.get('/api/admin/users').status_code,403)
        self.assertEqual(admin.patch('/api/admin/users/'+qb['user']['id'],json={'active':False}).status_code,200)
        self.assertEqual(b.get('/api/me').status_code,401)
        self.assertEqual(a.patch('/api/stamps/'+sid,json={**stamp,'width':40,'height':40}).status_code,200)
        from urllib.parse import urlparse, parse_qs
        visitor=TestClient(app,headers={'Origin':'http://testserver'})
        qr=a.post('/api/phone-sign',json={'language':'zh'}).json()
        token=parse_qs(urlparse(qr['url']).fragment)['token'][0]
        self.assertTrue(qr['qr'].startswith('data:image/png;base64,'))
        self.assertEqual(visitor.get('/api/phone-sign/'+qr['id']).status_code,401)
        admin.patch('/api/admin/users/'+qb['user']['id'],json={'active':True})
        b.post('/api/login',json={'email':'bob@example.test','password':'Strong-test-password-2026'})
        self.assertEqual(b.get('/api/phone-sign/'+qr['id']).status_code,410)
        self.assertEqual(admin.post('/api/phone-sign',json={}).status_code,403)
        self.assertEqual(visitor.post('/api/phone-sign/submit',json={'token':token,'image':base64.b64encode(b'%PDF').decode()}).status_code,400)
        self.assertEqual(visitor.post('/api/phone-sign/submit',json={'token':token,'image':base64.b64encode(raw).decode()}).status_code,200)
        with database() as c:
            row=c.execute('SELECT cipher,token FROM phone_signatures WHERE id=?',(qr['id'],)).fetchone()
            self.assertNotEqual(row['cipher'],raw);self.assertNotEqual(row['token'],token)
        self.assertEqual(a.get('/api/phone-sign/'+qr['id']).json()['image'],base64.b64encode(raw).decode())
        self.assertEqual(a.delete('/api/phone-sign/'+qr['id']).status_code,200)
        self.assertEqual(visitor.post('/api/phone-sign/status',json={'token':token}).status_code,410)
        qr=a.post('/api/phone-sign',json={}).json()
        token=parse_qs(urlparse(qr['url']).fragment)['token'][0]
        with database() as c:c.execute('UPDATE phone_signatures SET expires=?',(now()-1,))
        self.assertEqual(visitor.post('/api/phone-sign/submit',json={'token':token,'image':base64.b64encode(raw).decode()}).status_code,410)
        self.assertNotIn('recovery',qa)
        payload={'email':'alice@example.test','password':'A-different-password-2026'}
        with patch.dict(os.environ,{'RESEND_API_KEY':'test-key'}), patch('server.main.httpx.post') as send:
            send.return_value=Mock(raise_for_status=Mock())
            self.assertEqual(a.post('/api/recovery-email',json=payload).status_code,200)
            code=re.search(r'(?<!\d)([0-9]{6})(?!\d)',send.call_args.kwargs['json']['text']).group(1)
            self.assertEqual(a.post('/api/recovery-email',json=payload).status_code,200)
            self.assertEqual(send.call_count,1)
            self.assertEqual(a.post('/api/recover',json={**payload,'email':'bob@example.test','code':code}).status_code,400)
            self.assertEqual(a.post('/api/recover',json={**payload,'code':'wrong'}).status_code,400)
            self.assertEqual(a.post('/api/recover',json={**payload,'code':code}).status_code,200)
            self.assertEqual(a.get('/api/me').status_code,401)
            self.assertEqual(a.post('/api/recover',json={**payload,'code':code}).status_code,400)
            self.assertEqual(a.post('/api/login',json=payload).status_code,200)
            with database() as c:c.execute('DELETE FROM rate_limits')
            self.assertEqual(a.post('/api/recovery-email',json=payload).status_code,200)
            code=re.search(r'(?<!\d)([0-9]{6})(?!\d)',send.call_args.kwargs['json']['text']).group(1)
            for _ in range(5):self.assertEqual(a.post('/api/recover',json={**payload,'code':'wrong'}).status_code,400)
            self.assertEqual(a.post('/api/recover',json={**payload,'code':code}).status_code,400)
            with database() as c:
                c.execute('UPDATE email_codes SET attempts=0,expires=?',(now()-1,))
            self.assertEqual(a.post('/api/recover',json={**payload,'code':code}).status_code,400)
            with database() as c:c.execute('DELETE FROM email_codes')
            send.side_effect=RuntimeError('provider unavailable')
            self.assertEqual(a.post('/api/recovery-email',json=payload).status_code,502)
            with database() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM email_codes').fetchone()[0],0)

if __name__=='__main__':unittest.main()
