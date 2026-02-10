"""Handler para Vercel Serverless Functions."""
import sys
from pathlib import Path

# Adicionar raiz do projeto ao path
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

from app import app

def handler(request):
    """WSGI handler para Vercel."""
    return app(request)
