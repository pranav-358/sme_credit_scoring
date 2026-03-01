"""
Run this once after Module 6 to add the new explanation_json column.
WARNING: This drops and recreates all tables (dev only).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app import create_app
from extensions import db

app = create_app()
with app.app_context():
    db.drop_all()
    db.create_all()
    print("Database reset complete. All tables recreated.")