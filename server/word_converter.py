"""Isolated Word conversion service. No credentials, database or document archive."""
import asyncio,io,os,signal,tempfile,zipfile,logging
from pathlib import Path
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import Response

app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
lock=asyncio.Lock()
MAX_INPUT=8*1024*1024
MAX_OUTPUT=50*1024*1024

def validate_word(raw,kind):
    if kind=='doc':
        if not raw.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):raise ValueError('WORD_INVALID')
    elif kind=='docx':
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                entries=z.infolist();names={i.filename for i in entries}
                if len(entries)>2000 or sum(i.file_size for i in entries)>100*1024*1024:raise ValueError('WORD_LIMIT')
                if not {'[Content_Types].xml','word/document.xml'}.issubset(names):raise ValueError('WORD_INVALID')
                if any('vbaproject' in n.lower() for n in names):raise ValueError('WORD_MACRO')
        except (zipfile.BadZipFile,RuntimeError):raise ValueError('WORD_INVALID')
    else:raise ValueError('WORD_INVALID')

async def convert_word(raw,kind):
    validate_word(raw,kind)
    # This service runs with a private RAM-backed /tmp. No caller filenames are used.
    with tempfile.TemporaryDirectory(prefix='bsign-word-') as directory:
        root=Path(directory);source=root/('input.'+kind);source.write_bytes(raw)
        profile=root/'profile';(profile/'user').mkdir(parents=True)
        (profile/'user'/'registrymodifications.xcu').write_text('''<?xml version="1.0" encoding="UTF-8"?><oor:items xmlns:oor="http://openoffice.org/2001/registry"><item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item></oor:items>''')
        proc=None
        try:
            proc=await asyncio.create_subprocess_exec('/usr/bin/libreoffice','-env:UserInstallation='+profile.as_uri(),'--headless','--nologo','--nodefault','--norestore','--convert-to','pdf:writer_pdf_Export','--outdir',str(root),str(source),stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL,start_new_session=True,env={'PATH':'/usr/bin:/bin','HOME':str(root),'TMPDIR':str(root),'LANG':'C.UTF-8'})
            try:await asyncio.wait_for(proc.wait(),timeout=60)
            except asyncio.TimeoutError:raise ValueError('WORD_TIMEOUT')
            output=root/'input.pdf'
            if proc.returncode or not output.is_file():raise ValueError('WORD_CONVERT')
            if output.stat().st_size>MAX_OUTPUT:raise ValueError('WORD_LIMIT')
            pdf=output.read_bytes()
            if not pdf.startswith(b'%PDF-'):raise ValueError('WORD_CONVERT')
            return pdf
        finally:
            if proc:
                try:os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                await proc.wait()

@app.post('/convert')
async def convert(request:Request):
    if lock.locked():raise HTTPException(503,'WORD_BUSY')
    async with lock:
        raw=bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>MAX_INPUT:raise HTTPException(413,'WORD_LIMIT')
        try:pdf=await convert_word(bytes(raw),request.headers.get('x-word-format',''))
        except ValueError as e:raise HTTPException(400,str(e))
        except OSError as e:
            logging.error('Word converter OS error: errno=%s',e.errno)
            raise HTTPException(503,'WORD_UNAVAILABLE')
        return Response(pdf,media_type='application/pdf',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
