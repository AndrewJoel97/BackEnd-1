#!/usr/bin/env python
import sys
import os

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def root():
    return {"ok": True, "message": "API Competencias OK"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5002, log_level="info")