#!/usr/bin/env python3
"""Migra registros da base SQLite local para Firestore.

Uso:
  - Coloque o `serviceAccount.json` em `/workspaces/validacao-tempo/serviceAccount.json`
  - Exporte `USE_FIREBASE=1` e `FIREBASE_CREDENTIALS` (ou `GOOGLE_APPLICATION_CREDENTIALS`)
  - Rode: `python scripts/migrate_sqlite_to_firestore.py`

O script vai ler a tabela `professores` e inserir documentos na coleção
`professores` do Firestore usando `db_layer.insert_professor`.
"""
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import db_layer
except Exception as e:
    print("Erro ao importar db_layer:", e)
    raise

if not db_layer.USE_FIREBASE:
    print("USE_FIREBASE não está habilitado. Exporte USE_FIREBASE=1 e carregue as credenciais.")
    raise SystemExit(1)

db_path = ROOT / "dados" / "fundef.db"
if not db_path.exists():
    print(f"Arquivo SQLite não encontrado: {db_path}")
    raise SystemExit(1)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.execute("SELECT * FROM professores")
rows = cursor.fetchall()

print(f"Encontrados {len(rows)} registros em {db_path}. Iniciando migração...")
ok = 0
err = 0
for r in rows:
    data = {k: r[k] for k in r.keys()}
    # normalizações mínimas
    if isinstance(data.get("carga_horaria"), (int, float)):
        data["carga_horaria"] = int(data["carga_horaria"])
    try:
        db_layer.insert_professor(data)
        ok += 1
    except Exception as e:
        print(f"Erro ao migrar id={data.get('id')}: {e}")
        err += 1

print(f"Migração concluída. Sucesso: {ok}, Erros: {err}")
