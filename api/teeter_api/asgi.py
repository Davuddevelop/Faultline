"""The ASGI application, configured from the environment: what Vercel's
Python runtime serves (pyproject.toml, [tool.vercel]) and what any ASGI
server can run with 'uvicorn teeter_api.asgi:app'."""

from .app import create_app

app = create_app()
