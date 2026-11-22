"""Run from the repository root: python -m server.run."""
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1]/'.env')
from .main import app
from fastapi.staticfiles import StaticFiles
app.mount('/',StaticFiles(directory=Path(__file__).resolve().parents[1]/'app',html=True))
if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=int(os.environ.get('PORT','8090')),access_log=False)
