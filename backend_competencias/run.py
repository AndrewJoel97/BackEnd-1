#!/usr/bin/env python
import sys
import os

# Agregar el directorio actual al path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from app.main import app
    import uvicorn
    print("App imported successfully")

    if __name__ == "__main__":
        print("Starting uvicorn")
        try:
            uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
        except Exception as e:
            print(f"Error in uvicorn: {e}")
            import traceback
            traceback.print_exc()
        print("Uvicorn finished")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
