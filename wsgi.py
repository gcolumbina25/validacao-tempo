"""
WSGI entry point para Vercel
"""
from app import app

# Vercel procura por 'app' neste arquivo
if __name__ == "__main__":
    app.run()
