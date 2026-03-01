import sys
import os

# Add backend folder to Python path so imports work
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, 'backend')

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)