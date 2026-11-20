"""Entry point for uvicorn: `uvicorn latenote.main:app`."""

from .web import create_app

app = create_app()
