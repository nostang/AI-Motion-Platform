"""Development entry point: uvicorn api_main:app --reload --port 8000"""
from src.api.app import app

__all__ = ["app"]
