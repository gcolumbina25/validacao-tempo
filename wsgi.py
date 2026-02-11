"""
WSGI entry point para Vercel - com proteção máxima contra erros
"""
import sys
import os

try:
    from app import app
    # Sucesso - wsgi.app está pronto
except Exception as e:
    print(f"[FATAL] Erro ao importar app.py: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    
    # Criar app Flask minimal para retornar erro útil
    from flask import Flask
    app = Flask(__name__)
    
    @app.route("/")
    def error():
        return f"<h1>Erro ao carregar aplicação</h1><p>{str(e)}</p>", 500

if __name__ == "__main__":
    app.run()
