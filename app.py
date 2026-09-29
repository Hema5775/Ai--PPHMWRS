"""
Main Application Entry Point.
Runs development server or exposes WSGI app for production servers (e.g. Gunicorn/Waitress).
"""

import os
from app import create_app

env = os.getenv("FLASK_ENV", "development")
app = create_app(env)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")
    print(f"Starting AI Wellness Platform on http://127.0.0.1:{port} (env={env}, debug={debug})")
    app.run(host="0.0.0.0", port=port, debug=debug)
