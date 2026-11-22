"""Explicitly initialized BSign private CA; no automatic key replacement."""
import secrets
from datetime import datetime, timedelta, timezone
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
AAD=b'bsign-private-ca-v1'
def initialize(db,cipher):
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT id FROM private_ca WHERE id=1').fetchone(): return
        key=rsa.generate_private_key(public_exponent=65537,key_size=3072)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'BSign Community Private CA'),x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME,'Private CA; identity not verified')])
        now=datetime.now(timezone.utc)
        cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=3650)).add_extension(x509.BasicConstraints(ca=True,path_length=0),True).add_extension(x509.KeyUsage(False,False,False,False,False,True,True,None,None),True).add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()),False).add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),False).sign(key,hashes.SHA256()))
        nonce=secrets.token_bytes(12)
        raw=key.private_bytes(serialization.Encoding.DER,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        c.execute('INSERT INTO private_ca VALUES(1,?,?,?)',(nonce,cipher.encrypt(nonce,raw,AAD),cert.public_bytes(serialization.Encoding.DER)))
def load(db,cipher):
    with db() as c: row=c.execute('SELECT * FROM private_ca WHERE id=1').fetchone()
    if row is None: raise RuntimeError('Private CA is not initialized')
    key=serialization.load_der_private_key(cipher.decrypt(row['nonce'],row['cipher'],AAD),None)
    cert=x509.load_der_x509_certificate(row['cert'])
    if key.public_key().public_numbers()!=cert.public_key().public_numbers(): raise RuntimeError('CA key mismatch')
    if datetime.now(timezone.utc)>=cert.not_valid_after_utc: raise RuntimeError('CA expired')
    return key,cert
