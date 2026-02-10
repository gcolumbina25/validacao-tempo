#!/usr/bin/env bash
# Script de ajuda para configurar credenciais do Firebase localmente
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_PATH="$ROOT_DIR/serviceAccount.json"

if [ ! -f "$SERVICE_PATH" ]; then
  echo "Arquivo de credenciais não encontrado em: $SERVICE_PATH"
  echo "Coloque o serviceAccount JSON em $SERVICE_PATH (não compartilhe)."
  exit 1
fi

chmod 600 "$SERVICE_PATH" || true

echo "Configurando variáveis de ambiente temporárias para sessão atual..."
export FIREBASE_CREDENTIALS="$SERVICE_PATH"
export GOOGLE_APPLICATION_CREDENTIALS="$SERVICE_PATH"
export USE_FIREBASE=1

echo "Instalando dependências (se ainda não instalou)"
pip install -r "$ROOT_DIR/requirements.txt"

echo "Testando inicialização do módulo db_layer..."
python - <<PY
import sys
sys.path.insert(0, '.')
import db_layer
print('USE_FIREBASE =', db_layer.USE_FIREBASE)
print('Teste de inicialização concluído com sucesso.')
PY

echo "Pronto. Agora você pode executar o app:"
echo "  export FIREBASE_CREDENTIALS=$SERVICE_PATH"
echo "  export USE_FIREBASE=1"
echo "  python app.py"
