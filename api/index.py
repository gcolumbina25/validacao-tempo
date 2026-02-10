"""Handler WSGI para Vercel."""
import sys
from pathlib import Path

# Adicionar raiz do projeto ao path
root = Path(__file__).parent.parent
sys.path.insert(0, str(root))

# Importar Flask app
from app import app as wsgi_app

# Exportar como handler do Vercel
app = wsgi_app
