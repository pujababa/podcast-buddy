"""
Gunicorn Production Server Configuration for Render Deployment.
"""
import os

# Bind address: dynamically listen on Render's assigned $PORT
port = os.environ.get("PORT", "5000")
bind = f"0.0.0.0:{port}"

# Worker processes and threading model
# 2 workers with 4 threads each allow concurrent audio streaming and API requests
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("PYTHON_THREADS", "4"))
worker_class = "gthread"

# Timeout: generous 120s timeout to accommodate multi-speaker AI generation & TTS synthesis
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
keepalive = 5

# Ensure local bin (e.g. static ffmpeg) is discovered in PATH if present
local_bin = os.path.abspath("bin")
if os.path.isdir(local_bin) and local_bin not in os.environ.get("PATH", ""):
    os.environ["PATH"] = local_bin + os.pathsep + os.environ.get("PATH", "")

# Access and error logging
loglevel = os.environ.get("LOG_LEVEL", "info")
accesslog = "-"
errorlog = "-"

