"""BSign API: Standard edition: browser-local PDF signing and encrypted seal storage."""
import asyncio, qrcode
import hmac
import os, json, sqlite3, secrets, hashlib, base64, io, time, re, logging
from pathlib import Path
from urllib.parse import urlsplit
from contextlib import contextmanager, asynccontextmanager
from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from argon2 import PasswordHasher
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PIL import Image, ImageOps
import httpx
try:
    from .mail_templates import verification_mail
except ImportError:
    from mail_templates import verification_mail

DATA=Path(os.environ.get('BSIGN_DATA','./data')); DATA.mkdir(parents=True,exist_ok=True)
ORIGIN=os.environ.get('BSIGN_ORIGIN','http://127.0.0.1:8090').rstrip('/')
ALLOWED_ORIGINS={ORIGIN}|{v.strip().rstrip('/') for v in os.environ.get('BSIGN_ALLOWED_ORIGINS','').split(',') if v.strip()}
SECURE=ORIGIN.startswith('https://')
SESSION_COOKIE='bsign_session'
SESSION_PATH='/'
def request_origin(request):
    origin=request.headers.get('origin','')
    return origin if origin in ALLOWED_ORIGINS and urlsplit(origin).netloc==request.headers.get('host') else None
KEY=base64.b64decode(os.environ['BSIGN_MASTER_KEY'],validate=True)
if len(KEY)!=32: raise RuntimeError('BSIGN_MASTER_KEY must contain 32 random bytes')
CIPHER=AESGCM(KEY); PH=PasswordHasher(); DUMMY=PH.hash(secrets.token_hex(24))
ADMIN_EMAIL=os.environ.get('BSIGN_ADMIN_EMAIL','admin@example.test').strip().lower()
@asynccontextmanager
async def lifespan(app):
    async def sweep():
        while True:
            with db() as c:
                c.execute('BEGIN IMMEDIATE')
                c.execute('DELETE FROM phone_signatures WHERE expires<=?',(now(),))
            await asyncio.sleep(60)
    task=asyncio.create_task(sweep())
    try: yield
    finally:
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass

app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None,lifespan=lifespan)

@contextmanager
def db():
    c=sqlite3.connect(DATA/'bsign.db',timeout=20); c.row_factory=sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA journal_mode=WAL')
    try:
        yield c; c.commit()
    except Exception:
        c.rollback(); raise
    finally: c.close()

with db() as c:
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'user',active INTEGER NOT NULL DEFAULT 1,recovery TEXT NOT NULL,created INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,csrf TEXT,expires INTEGER);
    CREATE TABLE IF NOT EXISTS companies(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,created INTEGER);
    CREATE TABLE IF NOT EXISTS stamps(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,name TEXT NOT NULL,kind TEXT NOT NULL,width REAL NOT NULL,height REAL NOT NULL,nonce BLOB NOT NULL,cipher BLOB NOT NULL,created INTEGER);
    CREATE TABLE IF NOT EXISTS rate_limits(bucket TEXT PRIMARY KEY,count INTEGER,until INTEGER);
    CREATE TABLE IF NOT EXISTS resets(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id) ON DELETE CASCADE,expires INTEGER);
    CREATE TABLE IF NOT EXISTS email_codes(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,token TEXT NOT NULL,expires INTEGER NOT NULL,attempts INTEGER NOT NULL,sent INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS registration_codes(email TEXT PRIMARY KEY,token TEXT NOT NULL,expires INTEGER NOT NULL,attempts INTEGER NOT NULL,sent INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS verified_emails(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,verified INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS preferences(user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,language TEXT NOT NULL CHECK(language IN ('en','zh')));
    CREATE TABLE IF NOT EXISTS phone_signatures(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,token TEXT UNIQUE NOT NULL,expires INTEGER NOT NULL,nonce BLOB,cipher BLOB);
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor TEXT,target TEXT,action TEXT,created INTEGER);
    CREATE TABLE IF NOT EXISTS private_ca(id INTEGER PRIMARY KEY CHECK(id=1),nonce BLOB NOT NULL,cipher BLOB NOT NULL,cert BLOB NOT NULL);
    CREATE TABLE IF NOT EXISTS certificates(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,name TEXT NOT NULL,fingerprint TEXT NOT NULL,created INTEGER NOT NULL,expires INTEGER NOT NULL,nonce BLOB NOT NULL,cipher BLOB NOT NULL);
    ''')
    if 'source' not in [r['name'] for r in c.execute('PRAGMA table_info(certificates)')]:
        c.execute("ALTER TABLE certificates ADD COLUMN source TEXT NOT NULL DEFAULT 'self-signed'")


def digest(s): return hashlib.sha256(s.encode()).hexdigest()
def fail(msg,status=400): raise HTTPException(status,msg)
def now(): return int(time.time())
def rate(request,action,limit=15):
    ip=request.headers.get('x-real-ip') or request.client.host
    bucket=digest(action+':'+ip)
    with db() as c:
        c.execute('DELETE FROM rate_limits WHERE until<?',(now(),))
        c.execute('INSERT INTO rate_limits VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1',(bucket,now()+900))
        n=c.execute('SELECT count FROM rate_limits WHERE bucket=?',(bucket,)).fetchone()[0]
    if n>limit: fail('Too many attempts. Try again in 15 minutes.',429)

@app.middleware('http')
async def security(request,call_next):
    path=request.url.path
    if int(request.headers.get('content-length','0') or 0)>8*1024*1024:
        return JSONResponse({'detail':'Request too large'},status_code=413)
    if request.method not in ('GET','HEAD','OPTIONS') and not request_origin(request):
        return JSONResponse({'detail':'Invalid request origin'},status_code=403)
    response=await call_next(request)
    response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    return response

def auth(request:Request):
    token=request.cookies.get(SESSION_COOKIE,'')
    with db() as c:
        u=c.execute('SELECT u.*,s.csrf FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token=? AND s.expires>? AND u.active=1',(digest(token),now())).fetchone()
    if not u: fail('Please sign in.',401)
    if request.method not in ('GET','HEAD') and not secrets.compare_digest(request.headers.get('x-csrf-token',''),u['csrf']): fail('Invalid session request.',403)
    return dict(u)

def member(u=Depends(auth)):
    if u['role']!='user': fail('Administrators manage users only.',403)
    return u
def admin(u=Depends(auth)):
    if u['role']!='admin': fail('Administrator access required.',403)
    return u
def public(u):
    with db() as c: preference=c.execute('SELECT language FROM preferences WHERE user_id=?',(u['id'],)).fetchone()
    return {**{k:u[k] for k in ('id','email','name','role','active','created')},'language':preference['language'] if preference else None}

@app.post('/api/convert-word')
async def convert_word_document(request:Request,u=Depends(member)):
    rate(request,'word-convert:'+u['id'],20)
    kind=request.headers.get('x-word-format','')
    if kind not in ('doc','docx'):fail('WORD_INVALID')
    raw=bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw)>8*1024*1024:fail('WORD_LIMIT',413)
    transport=httpx.AsyncHTTPTransport(uds='/run/bsign-converter/converter.sock')
    try:
        async with httpx.AsyncClient(transport=transport,timeout=75) as client:
            response=await client.post('http://converter/convert',content=bytes(raw),headers={'X-Word-Format':kind,'Content-Type':'application/octet-stream'})
    except httpx.TimeoutException:fail('WORD_TIMEOUT',504)
    except httpx.RequestError:fail('WORD_UNAVAILABLE',503)
    if response.status_code!=200:
        try:detail=response.json().get('detail','WORD_CONVERT')
        except Exception:detail='WORD_CONVERT'
        if detail not in ('WORD_INVALID','WORD_LIMIT','WORD_MACRO','WORD_TIMEOUT','WORD_CONVERT','WORD_UNAVAILABLE','WORD_BUSY'):detail='WORD_CONVERT'
        fail(detail,response.status_code if response.status_code in (400,413,503) else 502)
    if not response.content.startswith(b'%PDF-'):fail('WORD_CONVERT',502)
    return Response(response.content,media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="converted.pdf"','Cache-Control':'no-store'})

class Preferences(BaseModel):
    language:str

@app.patch('/api/preferences')
def preferences(q:Preferences,u=Depends(auth)):
    if q.language not in ('en','zh'): fail('Unsupported language.')
    with db() as c: c.execute('INSERT OR REPLACE INTO preferences VALUES(?,?)',(u['id'],q.language))
    return {'language':q.language}

def session(response,u):
    token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(32)
    with db() as c:
        c.execute('DELETE FROM sessions WHERE expires<?',(now(),))
        c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(digest(token),u['id'],csrf,now()+86400*7))
    response.set_cookie(SESSION_COOKIE,token,httponly=True,secure=SECURE,samesite='strict',max_age=86400*7,path=SESSION_PATH)
    return {'user':public(u),'csrf':csrf}

class Credentials(BaseModel):
    email:str=Field(max_length=254)
    password:str=Field(min_length=1,max_length=128)
    name:str=Field(default='',max_length=80)
    token:str=Field(default='',max_length=256)
    code:str=Field(default='',max_length=6)
    language:str=Field(default='en',pattern='^(en|zh)$')
def email(s):
    s=s.strip().lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',s): fail('Enter a valid email address.')
    return s
def password(s):
    if len(s)<12: fail('Use a password with at least 12 characters.')
def create_user(q,role,connection=None):
    address=email(q.email);password(q.password)
    recovery=secrets.token_urlsafe(24)
    u={'id':secrets.token_hex(16),'email':address,'name':q.name.strip() or address.split('@')[0],'password':PH.hash(q.password),'role':role,'active':1,'recovery':digest(recovery),'created':now()}
    try:
        if connection is not None:
            connection.execute('INSERT INTO users VALUES(:id,:email,:name,:password,:role,:active,:recovery,:created)',u)
        else:
            with db() as c: c.execute('INSERT INTO users VALUES(:id,:email,:name,:password,:role,:active,:recovery,:created)',u)
    except sqlite3.IntegrityError: fail('This email is unavailable.',409)
    return u,recovery

@app.get('/api/health')
def health(): return {'ok':True}
@app.get('/api/config')
def config(): return {'emailRecovery':bool(os.environ.get('RESEND_API_KEY') and os.environ.get('RESEND_FROM')),'adminEmail':ADMIN_EMAIL}
@app.post('/api/register')
def register(q:Credentials,request:Request,response:Response):
    rate(request,'register',5)
    address=email(q.email);password(q.password)
    if address==ADMIN_EMAIL: fail('This address is reserved.',403)
    valid=False
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        challenge=c.execute('SELECT * FROM registration_codes WHERE email=?',(address,)).fetchone()
        if challenge and challenge['expires']>now() and challenge['attempts']<5:
            c.execute('UPDATE registration_codes SET attempts=attempts+1 WHERE email=?',(address,))
            valid=secrets.compare_digest(challenge['token'],registration_digest(address,q.code.strip()))
        if valid:
            u,_=create_user(q,'user',c)
            c.execute('DELETE FROM registration_codes WHERE email=?',(address,))
            c.execute('INSERT INTO verified_emails VALUES(?,?)',(u['id'],now()))
            c.execute('INSERT INTO preferences VALUES(?,?)',(u['id'],q.language))
    if not valid: fail('Invalid or expired verification code. Request a new code.')
    return session(response,u)
@app.post('/api/bootstrap')
def bootstrap(q:Credentials,request:Request,response:Response):
    rate(request,'bootstrap',5)
    expected=os.environ.get('BSIGN_BOOTSTRAP_TOKEN','')
    if not expected or not secrets.compare_digest(q.token,expected): fail('Invalid setup token.',403)
    with db() as c:
        if c.execute("SELECT 1 FROM users WHERE role='admin'").fetchone(): fail('Administrator is already configured.',409)
    q.email=ADMIN_EMAIL;u,_=create_user(q,'admin');return session(response,u)
@app.post('/api/login')
def login(q:Credentials,request:Request,response:Response):
    rate(request,'login',25)
    with db() as c: u=c.execute('SELECT * FROM users WHERE email=?',(q.email.strip().lower(),)).fetchone()
    try: valid=PH.verify(u['password'] if u else DUMMY,q.password)
    except Exception: valid=False
    if not u or not valid or not u['active']: fail('Email or password is incorrect, or account is unavailable.',401)
    return session(response,dict(u))
@app.get('/api/me')
def me(u=Depends(auth)): return {'user':public(u),'csrf':u['csrf']}
@app.post('/api/logout')
def logout(request:Request,response:Response,u=Depends(auth)):
    with db() as c: c.execute('DELETE FROM sessions WHERE token=?',(digest(request.cookies.get(SESSION_COOKIE,'')),))
    response.delete_cookie(SESSION_COOKIE,path=SESSION_PATH);return {'ok':True}

class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1,max_length=80)
    language: str

@app.patch('/api/profile')
def update_profile(q:ProfileUpdate,u=Depends(auth)):
    name=q.name.strip()
    if not name: fail('Name is required.')
    if q.language not in ('en','zh'): fail('Unsupported language.')
    with db() as c:
        c.execute('UPDATE users SET name=? WHERE id=?',(name,u['id']))
        c.execute('INSERT OR REPLACE INTO preferences VALUES(?,?)',(u['id'],q.language))
    return {'user':public({**u,'name':name})}

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1,max_length=128)
    new_password: str = Field(min_length=12,max_length=128)

@app.post('/api/password')
def change_password(q:PasswordChange,request:Request,u=Depends(auth)):
    rate(request,'password-change:'+u['id'],10)
    try: valid=PH.verify(u['password'],q.current_password)
    except Exception: valid=False
    if not valid: fail('Current password is incorrect.')
    if q.current_password==q.new_password: fail('Choose a different new password.')
    password(q.new_password)
    new_hash=PH.hash(q.new_password)
    token=digest(request.cookies.get('bsign_session',''))
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        changed=c.execute('UPDATE users SET password=?,recovery=? WHERE id=? AND password=? AND active=1',(new_hash,digest(secrets.token_urlsafe(32)),u['id'],u['password'])).rowcount
        if changed!=1: fail('Account changed. Sign in again and retry.',409)
        c.execute('DELETE FROM sessions WHERE user_id=? AND token<>?',(u['id'],token))
        c.execute('DELETE FROM resets WHERE user_id=?',(u['id'],))
        c.execute('DELETE FROM email_codes WHERE user_id=?',(u['id'],))
        c.execute('INSERT INTO audit(actor,target,action,created) VALUES(?,?,?,?)',(u['id'],u['id'],'password-changed',now()))
    return {'ok':True}


class Recovery(BaseModel):
    email:str=Field(max_length=254)
    code:str=Field(default='',max_length=256)
    password:str=Field(default='',max_length=128)
    language:str=Field(default='en',pattern='^(en|zh)$')

def registration_digest(address,code):
    return hmac.new(KEY,('registration:'+address+':'+code).encode(),hashlib.sha256).hexdigest()

def send_verification(address,token,purpose,language,request):
    content=verification_mail(token,purpose,language,request_origin(request) or ORIGIN)
    result=httpx.post('https://api.resend.com/emails',headers={'Authorization':'Bearer '+os.environ['RESEND_API_KEY'],'User-Agent':'BSign/1.0'},json={'from':os.environ['RESEND_FROM'],'to':[address],**content},timeout=15)
    result.raise_for_status()

@app.post('/api/registration-email')
def registration_email(q:Recovery,request:Request):
    rate(request,'registration-email',5)
    address=email(q.email)
    if not os.environ.get('RESEND_API_KEY') or not os.environ.get('RESEND_FROM'): fail('Email delivery is temporarily unavailable. Please try again later.',503)
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute('DELETE FROM registration_codes WHERE sent<?',(now()-86400,))
        if address==ADMIN_EMAIL or c.execute('SELECT 1 FROM users WHERE email=?',(address,)).fetchone():
            return {'ok':True,'retryAfter':60}
        previous=c.execute('SELECT sent FROM registration_codes WHERE email=?',(address,)).fetchone()
        if previous and now()-previous['sent']<60: return {'ok':True,'retryAfter':60-(now()-previous['sent'])}
        token=f'{secrets.randbelow(1000000):06d}'
        hashed=registration_digest(address,token)
        c.execute('INSERT OR REPLACE INTO registration_codes VALUES(?,?,0,0,?)',(address,hashed,now()))
    try:
        send_verification(address,token,'register',q.language,request)
        with db() as c: c.execute('UPDATE registration_codes SET expires=? WHERE email=? AND token=?',(now()+600,address,hashed))
    except Exception:
        with db() as c: c.execute('DELETE FROM registration_codes WHERE email=? AND token=?',(address,hashed))
        logging.warning('Registration email delivery failed')
        fail('Email delivery failed. Please try again later.',502)
    return {'ok':True,'retryAfter':60}
def code_digest(uid,code):
    return hmac.new(KEY,('password-reset:'+uid+':'+code).encode(),hashlib.sha256).hexdigest()

@app.post('/api/recover')
def recover(q:Recovery,request:Request):
    rate(request,'recover',15);password(q.password)
    address=email(q.email);valid=False
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        u=c.execute('SELECT * FROM users WHERE email=? AND active=1',(address,)).fetchone()
        reset=c.execute('SELECT * FROM email_codes WHERE user_id=?',(u['id'],)).fetchone() if u else None
        if reset and reset['expires']>now() and reset['attempts']<5:
            c.execute('UPDATE email_codes SET attempts=attempts+1 WHERE user_id=?',(u['id'],))
            valid=secrets.compare_digest(reset['token'],code_digest(u['id'],q.code.strip()))
        if valid:
            c.execute('UPDATE users SET password=?,recovery=? WHERE id=?',(PH.hash(q.password),digest(secrets.token_urlsafe(32)),u['id']))
            c.execute('DELETE FROM sessions WHERE user_id=?',(u['id'],))
            c.execute('DELETE FROM resets WHERE user_id=?',(u['id'],))
            c.execute('DELETE FROM email_codes WHERE user_id=?',(u['id'],))
    if not valid: fail('Invalid or expired verification code. Request a new code.',400)
    return {'ok':True}

@app.post('/api/recovery-email')
def recovery_email(q:Recovery,request:Request):
    rate(request,'recovery-email',5)
    address=email(q.email)
    key=os.environ.get('RESEND_API_KEY')
    if not key or not os.environ.get('RESEND_FROM'): fail('Email delivery is temporarily unavailable. Please try again later.',503)
    failed=False
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        u=c.execute('SELECT id FROM users WHERE email=? AND active=1',(address,)).fetchone()
        if u:
            previous=c.execute('SELECT sent FROM email_codes WHERE user_id=?',(u['id'],)).fetchone()
            if previous and now()-previous['sent']<60: return {'ok':True,'retryAfter':60}
            token=f'{secrets.randbelow(1000000):06d}'
            c.execute('INSERT OR REPLACE INTO email_codes VALUES(?,?,?,0,?)',(u['id'],code_digest(u['id'],token),0,now()))
    if u:
        try:
            send_verification(address,token,'recover',q.language,request)
            with db() as c:
                c.execute('UPDATE email_codes SET expires=? WHERE user_id=? AND token=?',(now()+600,u['id'],code_digest(u['id'],token)))
            logging.info('Password reset email accepted by provider')
        except Exception:
            logging.warning('Password reset email delivery failed')
            with db() as c:
                c.execute('DELETE FROM email_codes WHERE user_id=? AND token=?',(u['id'],code_digest(u['id'],token)))
            failed=True
    if failed: fail('Email delivery failed. Please try again later.',502)
    return {'ok':True,'retryAfter':60}

class Company(BaseModel):
    name:str=Field(min_length=1,max_length=100)
def owns_company(c,uid,cid):
    if not c.execute('SELECT id FROM companies WHERE id=? AND user_id=?',(cid,uid)).fetchone(): fail('Company not found.',404)
@app.get('/api/companies')
def companies(u=Depends(member)):
    with db() as c: return [dict(x) for x in c.execute('SELECT id,name,created FROM companies WHERE user_id=? ORDER BY created,id',(u['id'],))]
@app.post('/api/companies')
def new_company(q:Company,u=Depends(member)):
    name=q.name.strip()
    if not name: fail('Company name is required.')
    key=secrets.token_hex(16)
    with db() as c:
        if c.execute('SELECT COUNT(*) FROM companies WHERE user_id=?',(u['id'],)).fetchone()[0]>=50: fail('Company limit reached.')
        c.execute('INSERT INTO companies VALUES(?,?,?,?)',(key,u['id'],name,now()))
    return {'id':key,'name':name}
@app.patch('/api/companies/{cid}')
def edit_company(cid:str,q:Company,u=Depends(member)):
    if not q.name.strip(): fail('Company name is required.')
    with db() as c: owns_company(c,u['id'],cid);c.execute('UPDATE companies SET name=? WHERE id=?',(q.name.strip(),cid))
    return {'ok':True}
@app.delete('/api/companies/{cid}')
def delete_company(cid:str,u=Depends(member)):
    with db() as c: owns_company(c,u['id'],cid);c.execute('DELETE FROM companies WHERE id=?',(cid,))
    return {'ok':True}

class Stamp(BaseModel):
    name:str=Field(min_length=1,max_length=80)
    kind:str
    width:float=Field(ge=5,le=100,allow_inf_nan=False)
    height:float=Field(ge=3,le=100,allow_inf_nan=False)
    image:str=Field(default='',max_length=7500000)
def validate_stamp(q):
    if not q.name.strip() or q.kind not in ('round','square','signature'): fail('Invalid stamp details.')
    if q.kind in ('round','square') and abs(q.width-q.height)>.01: fail('Use equal width and height for round or square seals.')
def image_bytes(text):
    try:
        raw=base64.b64decode(text,validate=True)
        if len(raw)>5*1024*1024: fail('Image must be below 5 MB.')
        im=Image.open(io.BytesIO(raw))
        if im.format not in ('PNG','JPEG','WEBP') or im.width*im.height>16000000: fail('Use a PNG, JPEG or WebP below 16 megapixels.')
        im=ImageOps.exif_transpose(im).convert('RGBA')
        if min(im.size)<10: fail('Image is too small.')
        out=io.BytesIO();im.save(out,'PNG');return out.getvalue()
    except HTTPException: raise
    except Exception: fail('Invalid image.')
@app.get('/api/companies/{cid}/stamps')
def stamps(cid:str,u=Depends(member)):
    with db() as c:
        owns_company(c,u['id'],cid)
        return [dict(x) for x in c.execute('SELECT id,name,kind,width,height,created FROM stamps WHERE company_id=? AND user_id=? ORDER BY created ASC,rowid ASC',(cid,u['id']))]
@app.post('/api/companies/{cid}/stamps')
def create_stamp(cid:str,q:Stamp,u=Depends(member)):
    validate_stamp(q);raw=image_bytes(q.image);key=secrets.token_hex(16);nonce=os.urandom(12)
    aad=(u['id']+':'+cid+':'+key).encode();cipher=CIPHER.encrypt(nonce,raw,aad)
    with db() as c:
        owns_company(c,u['id'],cid)
        if c.execute('SELECT COUNT(*) FROM stamps WHERE user_id=?',(u['id'],)).fetchone()[0]>=300: fail('Stamp limit reached.')
        c.execute('INSERT INTO stamps VALUES(?,?,?,?,?,?,?,?,?,?)',(key,u['id'],cid,q.name.strip(),q.kind,q.width,q.height,nonce,cipher,now()))
    return {'id':key}
@app.get('/api/stamps/{sid}/image')
def stamp_image(sid:str,u=Depends(member)):
    with db() as c: r=c.execute('SELECT * FROM stamps WHERE id=? AND user_id=?',(sid,u['id'])).fetchone()
    if not r: fail('Stamp not found.',404)
    aad=(u['id']+':'+r['company_id']+':'+sid).encode()
    return Response(CIPHER.decrypt(r['nonce'],r['cipher'],aad),media_type='image/png')
@app.patch('/api/stamps/{sid}')
def edit_stamp(sid:str,q:Stamp,u=Depends(member)):
    validate_stamp(q)
    with db() as c:
        record=c.execute('SELECT kind,company_id FROM stamps WHERE id=? AND user_id=?',(sid,u['id'])).fetchone()
        if not record: fail('Stamp not found.',404)
        if record['kind']!=q.kind: fail('Seal type cannot be changed after saving.')
        c.execute('UPDATE stamps SET name=?,width=?,height=? WHERE id=?',(q.name.strip(),q.width,q.height,sid))
        if q.image:
            raw=image_bytes(q.image);nonce=os.urandom(12)
            aad=(u['id']+':'+record['company_id']+':'+sid).encode()
            cipher=CIPHER.encrypt(nonce,raw,aad)
            c.execute('UPDATE stamps SET nonce=?,cipher=? WHERE id=? AND user_id=?',(nonce,cipher,sid,u['id']))
    return {'ok':True}
@app.delete('/api/stamps/{sid}')
def delete_stamp(sid:str,u=Depends(member)):
    with db() as c:
        result=c.execute('DELETE FROM stamps WHERE id=? AND user_id=?',(sid,u['id']))
        if not result.rowcount: fail('Stamp not found.',404)
    return {'ok':True}

class UserUpdate(BaseModel):
    active:bool
@app.get('/api/admin/users')
def users(u=Depends(admin)):
    with db() as c: return [public(dict(x)) for x in c.execute('SELECT * FROM users ORDER BY created DESC LIMIT 2000')]
@app.patch('/api/admin/users/{uid}')
def update_user(uid:str,q:UserUpdate,u=Depends(admin)):
    with db() as c:
        target=c.execute('SELECT role FROM users WHERE id=?',(uid,)).fetchone()
        if not target: fail('User not found.',404)
        if target['role']=='admin': fail('Administrator accounts cannot be suspended here.',403)
        c.execute('UPDATE users SET active=? WHERE id=?',(int(q.active),uid))
        c.execute('DELETE FROM sessions WHERE user_id=?',(uid,))
        c.execute('INSERT INTO audit(actor,target,action,created) VALUES(?,?,?,?)',(u['id'],uid,'enable' if q.active else 'suspend',now()))
    return {'ok':True}


class PhoneCreate(BaseModel):
    language:str='en'

class PhoneToken(BaseModel):
    token:str=Field(min_length=32,max_length=100)

class PhoneSubmit(PhoneToken):
    image:str=Field(max_length=2800000)

@app.post('/api/phone-sign')
def phone_create(q:PhoneCreate,request:Request,u=Depends(member)):
    rate(request,'phone-create',20)
    sid=secrets.token_hex(16);token=secrets.token_urlsafe(32);expires=now()+600
    with db() as c:
        c.execute('DELETE FROM phone_signatures WHERE expires<=? OR user_id=?',(now(),u['id']))
        c.execute('INSERT INTO phone_signatures(id,user_id,token,expires) VALUES(?,?,?,?)',(sid,u['id'],digest(token),expires))
    url=(request_origin(request) or ORIGIN)+'/phone.html#token='+token+'&lang='+('zh' if q.language=='zh' else 'en')
    out=io.BytesIO();qrcode.make(url).save(out,format='PNG')
    return {'id':sid,'url':url,'expires':expires,'qr':'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()}

def phone_record(c,token):
    row=c.execute('SELECT p.* FROM phone_signatures p JOIN users u ON u.id=p.user_id WHERE p.token=? AND p.expires>? AND u.active=1',(digest(token),now())).fetchone()
    if not row: fail('This signing link has expired or been cancelled.',410)
    return row

@app.post('/api/phone-sign/status')
def phone_status(q:PhoneToken):
    with db() as c: row=phone_record(c,q.token)
    return {'submitted':row['cipher'] is not None,'expires':row['expires']}

@app.post('/api/phone-sign/submit')
def phone_submit(q:PhoneSubmit,request:Request):
    rate(request,'phone-submit',20)
    with db() as c: phone_record(c,q.token)
    raw=image_bytes(q.image)
    im=Image.open(io.BytesIO(raw))
    if not im.getchannel('A').getbbox(): fail('Write your signature first.')
    with db() as c:
        c.execute('BEGIN IMMEDIATE');row=phone_record(c,q.token)
        if row['cipher'] is not None: return {'ok':True}
        nonce=os.urandom(12)
        cipher=CIPHER.encrypt(nonce,raw,('phone:'+row['user_id']+':'+row['id']).encode())
        c.execute('UPDATE phone_signatures SET nonce=?,cipher=? WHERE id=?',(nonce,cipher,row['id']))
    return {'ok':True}

@app.get('/api/phone-sign/{sid}')
def phone_poll(sid:str,u=Depends(member)):
    with db() as c: row=c.execute('SELECT * FROM phone_signatures WHERE id=? AND user_id=? AND expires>?',(sid,u['id'],now())).fetchone()
    if not row: fail('This signing link has expired or been cancelled.',410)
    if row['cipher'] is None: return {'ready':False}
    raw=CIPHER.decrypt(row['nonce'],row['cipher'],('phone:'+u['id']+':'+sid).encode())
    return {'ready':True,'image':base64.b64encode(raw).decode()}

@app.delete('/api/phone-sign/{sid}')
def phone_cancel(sid:str,u=Depends(member)):
    with db() as c: c.execute('DELETE FROM phone_signatures WHERE id=? AND user_id=?',(sid,u['id']))
    return {'ok':True}


class NewCertificate(BaseModel):
    name: str = Field(min_length=1,max_length=80)
    password: str = Field(min_length=12,max_length=128)
    acknowledge: bool = False

@app.get('/api/certificates')
def certificates(u=Depends(member)):
    with db() as c: rows=c.execute('SELECT id,name,fingerprint,created,expires,source FROM certificates WHERE user_id=? ORDER BY created DESC',(u['id'],)).fetchall()
    return [dict(r) for r in rows]

@app.post('/api/certificates')
def create_certificate(q:NewCertificate,request:Request,u=Depends(member)):
    from datetime import datetime,timedelta,timezone
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes,serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    if not q.acknowledge: fail('Acknowledge that this certificate does not verify identity.')
    if not q.name.strip(): fail('Enter a certificate name.')
    rate(request,'certificate-create',10)
    with db() as c:
        if c.execute('SELECT COUNT(*) FROM certificates WHERE user_id=?',(u['id'],)).fetchone()[0]>=10: fail('Maximum 10 certificates. Delete an unused certificate first.')
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    start=datetime.now(timezone.utc);end=start+timedelta(days=365*3)
    try: from server.private_ca import load
    except ModuleNotFoundError: from private_ca import load
    try: ca_key,ca_cert=load(db,CIPHER)
    except Exception: fail('Certificate issuing is temporarily unavailable.',503)
    end=min(end,ca_cert.not_valid_after_utc)
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,q.name.strip()),x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME,'Identity not verified')])
    cert=(x509.CertificateBuilder().subject_name(subject).issuer_name(ca_cert.subject).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(start-timedelta(minutes=5)).not_valid_after(end).add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True).add_extension(x509.KeyUsage(digital_signature=True,content_commitment=False,key_encipherment=False,data_encipherment=False,key_agreement=False,key_cert_sign=False,crl_sign=False,encipher_only=None,decipher_only=None),critical=True).add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),False).sign(ca_key,hashes.SHA256()))
    raw=pkcs12.serialize_key_and_certificates(q.name.strip().encode(),key,cert,[ca_cert],serialization.BestAvailableEncryption(q.password.encode()))
    cid=secrets.token_hex(16);nonce=secrets.token_bytes(12);fingerprint=cert.fingerprint(hashes.SHA256()).hex()
    cipher=CIPHER.encrypt(nonce,raw,('certificate:'+u['id']+':'+cid).encode())
    with db() as c: c.execute('INSERT INTO certificates(id,user_id,name,fingerprint,created,expires,nonce,cipher,source) VALUES(?,?,?,?,?,?,?,?,?)',(cid,u['id'],q.name.strip(),fingerprint,now(),int(end.timestamp()),nonce,cipher,'bsign-ca'))
    return {'id':cid,'fingerprint':fingerprint}


class ImportCertificate(BaseModel):
    name: str = Field(min_length=1,max_length=80)
    password: str = Field(min_length=1,max_length=128)
    file: str = Field(max_length=2800000)

@app.post('/api/certificates/import')
def import_certificate(q:ImportCertificate,request:Request,u=Depends(member)):
    from datetime import datetime,timezone
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    rate(request,'certificate-import',10)
    if not q.name.strip(): fail('Enter a certificate name.')
    try:
        raw=base64.b64decode(q.file,validate=True)
        if len(raw)>2*1024*1024: fail('Use a P12/PFX smaller than 2 MB.')
        key,cert,chain=pkcs12.load_key_and_certificates(raw,q.password.encode())
    except HTTPException: raise
    except Exception: fail('Cannot open certificate. Check the file and password.')
    if not isinstance(key,rsa.RSAPrivateKey) or key.key_size<2048 or cert is None: fail('Use an RSA signing certificate with a key of at least 2048 bits.')
    if key.public_key().public_numbers()!=cert.public_key().public_numbers(): fail('Certificate and private key do not match.')
    current=datetime.now(timezone.utc)
    if not cert.not_valid_before_utc<=current<cert.not_valid_after_utc: fail('Certificate has expired or is not yet valid.')
    try:
        if cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca: fail('Use a signing certificate, not a CA certificate.')
    except x509.ExtensionNotFound: pass
    try:
        usage=cert.extensions.get_extension_for_class(x509.KeyUsage).value
        if not usage.digital_signature and not usage.content_commitment: fail('Certificate does not permit signing.')
    except x509.ExtensionNotFound: pass
    cid=secrets.token_hex(16);nonce=secrets.token_bytes(12);fingerprint=cert.fingerprint(hashes.SHA256()).hex()
    encrypted=CIPHER.encrypt(nonce,raw,('certificate:'+u['id']+':'+cid).encode())
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT COUNT(*) FROM certificates WHERE user_id=?',(u['id'],)).fetchone()[0]>=10: fail('Maximum 10 certificates. Delete an unused certificate first.')
        c.execute('INSERT INTO certificates(id,user_id,name,fingerprint,created,expires,nonce,cipher,source) VALUES(?,?,?,?,?,?,?,?,?)',(cid,u['id'],q.name.strip(),fingerprint,now(),int(cert.not_valid_after_utc.timestamp()),nonce,encrypted,'imported'))
    return {'id':cid,'fingerprint':fingerprint}

@app.get('/api/certificates/{cid}/download')
def download_certificate(cid:str,u=Depends(member)):
    with db() as c: row=c.execute('SELECT * FROM certificates WHERE id=? AND user_id=?',(cid,u['id'])).fetchone()
    if not row: fail('Certificate not found.',404)
    raw=CIPHER.decrypt(row['nonce'],row['cipher'],('certificate:'+u['id']+':'+cid).encode())
    return Response(raw,media_type='application/x-pkcs12',headers={'Content-Disposition':'attachment; filename="BSign-'+cid+'.p12"'})

@app.delete('/api/certificates/{cid}')
def delete_certificate(cid:str,u=Depends(member)):
    with db() as c:
        if c.execute('DELETE FROM certificates WHERE id=? AND user_id=?',(cid,u['id'])).rowcount!=1: fail('Certificate not found.',404)
    return {'ok':True}
