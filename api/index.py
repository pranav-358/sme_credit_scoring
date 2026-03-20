"""
api/index.py — Vercel serverless entry point
"""
import sys
import os

# Add backend to path
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app

app = create_app()

# Vercel needs the app object named 'app'
application = app