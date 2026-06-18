# routes/__init__.py
# Exposes Blueprint registration for app.py.

from .auth import auth_bp
from .api import api_bp
from .pages import pages_bp

__all__ = ["auth_bp", "api_bp", "pages_bp"]
