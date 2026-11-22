"""Explicitly initialize this deployment's own private CA."""
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1]/'.env')
from .main import db,CIPHER
from .private_ca import initialize,load
from cryptography.hazmat.primitives import hashes
initialize(db,CIPHER)
_,cert=load(db,CIPHER)
print('Private CA SHA-256:',cert.fingerprint(hashes.SHA256()).hex())
