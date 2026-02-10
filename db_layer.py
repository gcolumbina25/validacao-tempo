from __future__ import annotations

import os
from datetime import datetime
from typing import Any

# Padrão para desenvolvimento local é SQLite (USE_FIREBASE=0)
# Vercel sobrescreve com USE_FIREBASE=1 via vercel.json
USE_FIREBASE = os.environ.get("USE_FIREBASE", "0") == "1"

if USE_FIREBASE:
    import firebase_admin
    from firebase_admin import credentials, firestore
    import json
    import tempfile
    import base64

    cred = None
    firebase_initialized = False
    
    # Tenta carregar credenciais de arquivo (local dev)
    cred_path = os.environ.get("FIREBASE_CREDENTIALS")
    if cred_path and os.path.isfile(cred_path):
        try:
            cred = credentials.Certificate(cred_path)
            print("[Firebase] Credenciais carregadas de arquivo local")
        except Exception as e:
            print(f"[Firebase] Erro ao carregar credenciais de arquivo: {e}")
    
    # Tenta carregar credenciais de variável JSON ou base64 (Vercel/prod)
    if not cred:
        cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON")
        if cred_json:
            try:
                # Tenta decodificar como base64 primeiro
                try:
                    decoded = base64.b64decode(cred_json).decode('utf-8')
                    cred_dict = json.loads(decoded)
                    print("[Firebase] Credenciais decodificadas de base64")
                except Exception:
                    # Se falhar, tenta direto como JSON
                    cred_dict = json.loads(cred_json)
                    print("[Firebase] Credenciais carregadas como JSON")
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(cred_dict, f)
                    temp_cred_path = f.name
                cred = credentials.Certificate(temp_cred_path)
            except (json.JSONDecodeError, ValueError, base64.binascii.Error) as e:
                print(f"[Firebase] Erro ao decodificar FIREBASE_CREDENTIALS_JSON: {e}")
    
    # Se nenhuma credencial explícita, tenta Application Default Credentials
    if cred:
        try:
            firebase_admin.initialize_app(cred)
            firebase_initialized = True
            print("[Firebase] Aplicativo inicializado com sucesso")
        except ValueError as e:
            print(f"[Firebase] Erro ao inicializar com credenciais: {e}")
    else:
        try:
            firebase_admin.initialize_app()
            firebase_initialized = True
            print("[Firebase] Aplicativo inicializado com Application Default Credentials")
        except ValueError as e:
            print(f"[Firebase] Erro ao inicializar: {e}")

    if firebase_initialized:
        db = firestore.client()
        print("[Firebase] Cliente Firestore criado com sucesso")
    else:
        print("[Firebase] AVISO: Não foi possível inicializar Firebase!")


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Firestore implementation
if USE_FIREBASE:
    def init_db() -> None:
        meta_ref = db.collection("_meta").document("counters")
        if not meta_ref.get().exists:
            meta_ref.set({"last_professor_id": 0, "last_rascunho_id": 0})

    def _next_id(name: str) -> int:
        meta_ref = db.collection("_meta").document("counters")

        def transaction_increment(transaction):
            snapshot = meta_ref.get(transaction=transaction)
            data = snapshot.to_dict() or {}
            key = f"last_{name}_id"
            last = int(data.get(key, 0))
            novo = last + 1
            transaction.update(meta_ref, {key: novo})
            return novo

        return db.transaction()(transaction_increment)

    def list_professores(order_desc: bool = True) -> list[dict[str, Any]]:
        coll = db.collection("professores")
        query = coll.order_by("id", direction=firestore.Query.DESCENDING if order_desc else firestore.Query.ASCENDING)
        docs = query.stream()
        return [doc.to_dict() for doc in docs]

    def list_rascunhos() -> list[dict[str, Any]]:
        docs = db.collection("rascunhos_professores").order_by("atualizado_em", direction=firestore.Query.DESCENDING).stream()
        return [doc.to_dict() for doc in docs]

    def find_professor_by_cpf(cpf: str) -> dict[str, Any] | None:
        docs = db.collection("professores").where("cpf", "==", cpf).limit(1).stream()
        for d in docs:
            return d.to_dict()
        return None

    def get_professor(professor_id: int) -> dict[str, Any] | None:
        docs = db.collection("professores").where("id", "==", int(professor_id)).limit(1).stream()
        for d in docs:
            return d.to_dict()
        return None

    def insert_professor(data: dict[str, Any]) -> int:
        novo_id = _next_id("professor")
        payload = dict(data)
        payload["id"] = int(novo_id)
        payload["criado_em"] = _now_str()
        db.collection("professores").document(str(novo_id)).set(payload)
        return novo_id

    def update_professor(professor_id: int, data: dict[str, Any]) -> None:
        docs = db.collection("professores").where("id", "==", int(professor_id)).limit(1).stream()
        for d in docs:
            db.collection("professores").document(d.id).update(data)
            return

    def delete_professor(professor_id: int) -> None:
        docs = db.collection("professores").where("id", "==", int(professor_id)).limit(1).stream()
        for d in docs:
            db.collection("professores").document(d.id).delete()
            return

    def save_rascunho(dados: dict[str, Any], rascunho_id: int | None = None) -> int:
        if rascunho_id is None:
            novo = _next_id("rascunho")
            payload = dict(dados)
            payload["id"] = int(novo)
            payload["criado_em"] = _now_str()
            payload["atualizado_em"] = payload["criado_em"]
            db.collection("rascunhos_professores").document(str(novo)).set(payload)
            return novo
        else:
            docs = db.collection("rascunhos_professores").where("id", "==", int(rascunho_id)).limit(1).stream()
            for d in docs:
                payload = dict(dados)
                payload["atualizado_em"] = _now_str()
                db.collection("rascunhos_professores").document(d.id).update(payload)
                return int(rascunho_id)
            # se não existe, cria
            novo = int(rascunho_id)
            payload = dict(dados)
            payload["id"] = novo
            payload["criado_em"] = _now_str()
            payload["atualizado_em"] = payload["criado_em"]
            db.collection("rascunhos_professores").document(str(novo)).set(payload)
            return novo

    def carregar_rascunho(rascunho_id: int) -> dict[str, Any] | None:
        docs = db.collection("rascunhos_professores").where("id", "==", int(rascunho_id)).limit(1).stream()
        for d in docs:
            return d.to_dict()
        return None

    def remover_rascunho(rascunho_id: int) -> None:
        docs = db.collection("rascunhos_professores").where("id", "==", int(rascunho_id)).limit(1).stream()
        for d in docs:
            db.collection("rascunhos_professores").document(d.id).delete()
            return

    def export_professores() -> list[dict[str, Any]]:
        return list_professores(order_desc=True)

    def get_professores_for_rateio() -> list[dict[str, Any]]:
        docs = db.collection("professores").order_by("nome").stream()
        return [d.to_dict() for d in docs]

else:
    # SQLite fallback: manter comportamento atual (usar sqlite3)
    import sqlite3
    from pathlib import Path
    import sys

    BASE_DIR = (
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent
    )
    DATA_DIR = Path(os.environ["DATA_DIR"]).resolve() if os.environ.get("DATA_DIR") else BASE_DIR / "dados"
    DATABASE_PATH = DATA_DIR / "fundef.db"

    def get_connection() -> sqlite3.Connection:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
        except (OSError, IOError):
            pass  # Ignore if filesystem is read-only
        connection = sqlite3.connect(DATABASE_PATH)
        connection.row_factory = sqlite3.Row
        return connection

    def init_db() -> None:
        from sqlite3 import Connection

        with get_connection() as conn:  # type: Connection
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS professores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    cpf TEXT NOT NULL UNIQUE,
                    rg TEXT NOT NULL,
                    matricula TEXT NOT NULL,
                    escola TEXT NOT NULL,
                    cargo TEXT NOT NULL,
                    situacao_servidor TEXT NOT NULL,
                    data_admissao TEXT NOT NULL,
                    telefone TEXT NOT NULL,
                    email TEXT NOT NULL,
                    endereco TEXT NOT NULL,
                    banco TEXT NOT NULL,
                    agencia TEXT NOT NULL,
                    conta TEXT NOT NULL,
                    tipo_conta TEXT NOT NULL,
                    data_inicio_fundef TEXT NOT NULL,
                    data_fim_fundef TEXT NOT NULL,
                    carga_horaria INTEGER NOT NULL,
                    quantidade_meses_trabalhados INTEGER NOT NULL,
                    aceitou_declaracao INTEGER NOT NULL,
                    criado_em TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rascunhos_professores (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome_referencia TEXT NOT NULL DEFAULT '',
                    cpf TEXT NOT NULL DEFAULT '',
                    dados_json TEXT NOT NULL,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
                """
            )

    def list_professores(order_desc: bool = True) -> list[dict[str, Any]]:
        with get_connection() as conn:
            q = "SELECT * FROM professores ORDER BY id DESC" if order_desc else "SELECT * FROM professores ORDER BY id ASC"
            registros = conn.execute(q).fetchall()
            return [dict(r) for r in registros]

    def list_rascunhos() -> list[dict[str, Any]]:
        with get_connection() as conn:
            registros = conn.execute("SELECT id, nome_referencia, cpf, atualizado_em, criado_em FROM rascunhos_professores ORDER BY datetime(atualizado_em) DESC, id DESC").fetchall()
            return [dict(r) for r in registros]

    def find_professor_by_cpf(cpf: str) -> dict[str, Any] | None:
        with get_connection() as conn:
            r = conn.execute("SELECT * FROM professores WHERE cpf = ?", (cpf,)).fetchone()
            return dict(r) if r else None

    def get_professor(professor_id: int) -> dict[str, Any] | None:
        with get_connection() as conn:
            r = conn.execute("SELECT * FROM professores WHERE id = ?", (professor_id,)).fetchone()
            return dict(r) if r else None

    def insert_professor(data: dict[str, Any]) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO professores (
                    nome, cpf, rg, matricula, escola, cargo,
                    situacao_servidor, data_admissao, telefone, email, endereco,
                    banco, agencia, conta, tipo_conta,
                    data_inicio_fundef, data_fim_fundef,
                    carga_horaria, quantidade_meses_trabalhados,
                    aceitou_declaracao, criado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("nome"),
                    data.get("cpf"),
                    data.get("rg"),
                    data.get("matricula"),
                    data.get("escola"),
                    data.get("cargo"),
                    data.get("situacao_servidor"),
                    data.get("data_admissao"),
                    data.get("telefone"),
                    data.get("email"),
                    data.get("endereco"),
                    data.get("banco"),
                    data.get("agencia"),
                    data.get("conta"),
                    data.get("tipo_conta"),
                    data.get("data_inicio_fundef"),
                    data.get("data_fim_fundef"),
                    int(data.get("carga_horaria", 0)),
                    int(data.get("quantidade_meses_trabalhados", 0)),
                    int(data.get("aceitou_declaracao", 0)),
                    _now_str(),
                ),
            )
            return int(cursor.lastrowid)

    def update_professor(professor_id: int, data: dict[str, Any]) -> None:
        # For brevity, only update a subset used by application flows
        with get_connection() as conn:
            cols = [
                "nome", "cpf", "rg", "matricula", "escola", "cargo",
                "situacao_servidor", "data_admissao", "telefone", "email", "endereco",
                "banco", "agencia", "conta", "tipo_conta",
                "data_inicio_fundef", "data_fim_fundef", "carga_horaria",
                "quantidade_meses_trabalhados", "aceitou_declaracao",
            ]
            vals = [data.get(c) for c in cols]
            vals.append(professor_id)
            conn.execute(f"UPDATE professores SET {', '.join([c + ' = ?' for c in cols])} WHERE id = ?", tuple(vals))

    def delete_professor(professor_id: int) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM professores WHERE id = ?", (professor_id,))

    def save_rascunho(dados: dict[str, Any], rascunho_id: int | None = None) -> int:
        import json
        agora = _now_str()
        nome_referencia = dados.get("nome", "")
        cpf = dados.get("cpf", "")
        with get_connection() as conn:
            if rascunho_id is not None:
                existente = conn.execute("SELECT id FROM rascunhos_professores WHERE id = ?", (rascunho_id,)).fetchone()
                if existente:
                    conn.execute(
                        "UPDATE rascunhos_professores SET nome_referencia = ?, cpf = ?, dados_json = ?, atualizado_em = ? WHERE id = ?",
                        (nome_referencia, cpf, json.dumps(dados, ensure_ascii=False), agora, rascunho_id),
                    )
                    return int(rascunho_id)
            cursor = conn.execute(
                "INSERT INTO rascunhos_professores (nome_referencia, cpf, dados_json, criado_em, atualizado_em) VALUES (?, ?, ?, ?, ?)",
                (nome_referencia, cpf, json.dumps(dados, ensure_ascii=False), agora, agora),
            )
            return int(cursor.lastrowid)

    def carregar_rascunho(rascunho_id: int) -> dict[str, Any] | None:
        import json
        with get_connection() as conn:
            r = conn.execute("SELECT id, dados_json, criado_em, atualizado_em FROM rascunhos_professores WHERE id = ?", (rascunho_id,)).fetchone()
            if not r:
                return None
            try:
                payload = json.loads(r["dados_json"])
            except Exception:
                payload = {}
            return {"id": r["id"], "dados": payload, "criado_em": r["criado_em"], "atualizado_em": r["atualizado_em"]}

    def remover_rascunho(rascunho_id: int) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM rascunhos_professores WHERE id = ?", (rascunho_id,))

    def export_professores() -> list[dict[str, Any]]:
        with get_connection() as conn:
            registros = conn.execute("SELECT id, nome, cpf, rg, matricula, escola, cargo, situacao_servidor, data_admissao, telefone, email, endereco, banco, agencia, conta, tipo_conta, data_inicio_fundef, data_fim_fundef, carga_horaria, quantidade_meses_trabalhados, criado_em FROM professores ORDER BY id DESC").fetchall()
            return [dict(r) for r in registros]

    def get_professores_for_rateio() -> list[dict[str, Any]]:
        with get_connection() as conn:
            registros = conn.execute("SELECT id, nome, cpf, escola, cargo, situacao_servidor, quantidade_meses_trabalhados FROM professores ORDER BY nome ASC").fetchall()
            return [dict(r) for r in registros]
