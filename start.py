"""Railway entry point — reads PORT from environment."""
import os
import uvicorn

port = int(os.environ.get("PORT", "8000"))
uvicorn.run("signalapp.app.main:app", host="0.0.0.0", port=port)
