from __future__ import annotations

import os
import json
import tempfile
from datetime import datetime
from typing import Any

# NUNCA FALHA - proteção máxima contra exceções no import

USE_FIREBASE = os.environ.get("USE_FIREBASE", "0") == "1"

# Estado global - inicialização lazy
_firebase_ready = False
_db_instance = None
_fs = None  # firestore module

def ensure_firebase():
    """Inicializa Firebase se necessário - NUNCA lança exceção."""
    global _firebase_ready, _db_instance, _fs
    
    if _firebase_ready or not USE_FIREBASE:
        return _firebase_ready
    
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        _fs = firestore
        
        cred = None
        
        # Tentar carregar credenciais
        cred_json = os.environ.get("FIREBASE_CREDENTIALS_JSON", "")
        if cred_json.strip():
            try:
                import base64
                try:
                    decoded = base64.b64decode(cred_json).decode('utf-8')
                    cred_dict = json.loads(decoded)
                except:
                    cred_dict = json.loads(cred_json)
                
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(cred_dict, f)
                    temp_path = f.name
                
                cred = credentials.Certificate(temp_path)
                print(f"[Firebase] Credenciais carregadas de env var")
            except Exception as e:
                print(f"[Firebase WARN] Erro ao carregar credenciais env: {e}")
        
        # Se não conseguiu credenciais, tenta ADC
        if not cred:
            try:
                cred = credentials.ApplicationDefaultCredentials()
                print("[Firebase] Usando Application Default Credentials")
            except:
                pass
        
        # Se tem credenciais, inicializa app
        if cred:
            try:
                firebase_admin.initialize_app(cred)
                _db_instance = firestore.client()
                _firebase_ready = True
                print("[Firebase] ✓ Inicializado com sucesso")
            except Exception as e:
                print(f"[Firebase WARN] Erro ao inicializar app: {e}")
                _firebase_ready = False
        else:
            print("[Firebase WARN] Nenhuma credencial disponível")
            _firebase_ready = False
    
    except Exception as e:
        print(f"[Firebase WARN] Erro geral: {e}")
        _firebase_ready = False
    
    return _firebase_ready

class DBProxy:
    """Proxy que acessa Firestore ou retorna None se indisponível."""
    def __call__(self, *args, **kwargs):
        return self
    
    def collection(self, *args, **kwargs):
        if ensure_firebase() and _db_instance:
            return _db_instance.collection(*args, **kwargs)
        raise RuntimeError("Firebase não está disponível")
    
    def transaction(self, *args, **kwargs):
        if ensure_firebase() and _db_instance:
            return _db_instance.transaction(*args, **kwargs)
        raise RuntimeError("Firebase não está disponível")
    
    def batch(self):
        if ensure_firebase() and _db_instance:
            return _db_instance.batch()
        raise RuntimeError("Firebase não está disponível")
    
    def __getattr__(self, name):
        if ensure_firebase() and _db_instance:
            return getattr(_db_instance, name)
        raise RuntimeError(f"Firebase não está disponível para acessar {name}")

db = DBProxy()

def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Stubs de funções que podem falhar se Firebase não estiver disponível
def init_db() -> None:
    if not USE_FIREBASE:
        return  # SQLite não precisa inicializar
    try:
        meta_ref = db.collection("_meta").document("counters")
        if not meta_ref.get().exists:
            meta_ref.set({"last_professor_id": 0, "last_rascunho_id": 0})
    except Exception as e:
        print(f"[init_db] ERRO: {e}")

def _next_id(name: str) -> int:
    if not USE_FIREBASE:
        return 0
    try:
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
    except Exception as e:
        print(f"[_next_id] ERRO: {e}")
        return 0

def list_professores(order_desc: bool = True) -> list[dict[str, Any]]:
    if not USE_FIREBASE:
        return []
    try:
        coll = db.collection("professores")
        if _fs:
            query = coll.order_by("id", direction=_fs.Query.DESCENDING if order_desc else _fs.Query.ASCENDING)
        else:
            query = coll.order_by("id")
        docs = query.stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"[list_professores] ERRO: {e}")
        return []

def list_rascunhos() -> list[dict[str, Any]]:
    if not USE_FIREBASE:
        return []
    try:
        docs = db.collection("rascunhos_professores").order_by("atualizado_em", direction=_fs.Query.DESCENDING if _fs else None).stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"[list_rascunhos] ERRO: {e}")
        return []

def find_professor_by_cpf(cpf: str) -> dict[str, Any] | None:
    if not USE_FIREBASE:
        return None
    try:
        docs = db.collection("professores").where("cpf", "==", cpf).limit(1).stream()
        for d in docs:
            return d.to_dict()
    except Exception as e:
        print(f"[find_professor_by_cpf] ERRO: {e}")
    return None

def get_professor(professor_id: int) -> dict[str, Any] | None:
    if not USE_FIREBASE:
        return None
    try:
        docs = db.collection("professores").where("id", "==", int(professor_id)).limit(1).stream()
        for d in docs:
            return d.to_dict()
    except Exception as e:
        print(f"[get_professor] ERRO: {e}")
    return None

def insert_professor(prof_data: dict[str, Any]) -> int:
    if not USE_FIREBASE:
        return 0
    try:
        professor_id = _next_id("professor")
        prof_data["id"] = professor_id
        prof_data["criado_em"] = _now_str()
        db.collection("professores").document(str(professor_id)).set(prof_data)
        return professor_id
    except Exception as e:
        print(f"[insert_professor] ERRO: {e}")
        return 0

def update_professor(professor_id: int, updates: dict[str, Any]) -> bool:
    if not USE_FIREBASE:
        return False
    try:
        updates["atualizado_em"] = _now_str()
        db.collection("professores").document(str(professor_id)).update(updates)
        return True
    except Exception as e:
        print(f"[update_professor] ERRO: {e}")
        return False

def delete_professor(professor_id: int) -> bool:
    if not USE_FIREBASE:
        return False
    try:
        db.collection("professores").document(str(professor_id)).delete()
        return True
    except Exception as e:
        print(f"[delete_professor] ERRO: {e}")
        return False

def save_rascunho(user_id: str, form_data: dict[str, Any]) -> bool:
    if not USE_FIREBASE:
        return False
    try:
        form_data["atualizado_em"] = _now_str()
        db.collection("rascunhos_professores").document(user_id).set(form_data)
        return True
    except Exception as e:
        print(f"[save_rascunho] ERRO: {e}")
        return False

def carregar_rascunho(user_id: str) -> dict[str, Any] | None:
    if not USE_FIREBASE:
        return None
    try:
        doc = db.collection("rascunhos_professores").document(user_id).get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        print(f"[carregar_rascunho] ERRO: {e}")
    return None

def remover_rascunho(user_id: str) -> bool:
    if not USE_FIREBASE:
        return False
    try:
        db.collection("rascunhos_professores").document(user_id).delete()
        return True
    except Exception as e:
        print(f"[remover_rascunho] ERRO: {e}")
        return False

def export_professores() -> list[dict[str, Any]]:
    if not USE_FIREBASE:
        return []
    try:
        docs = db.collection("professores").stream()
        return [doc.to_dict() for doc in docs]
    except Exception as e:
        print(f"[export_professores] ERRO: {e}")
        return []

def get_professores_for_rateio() -> list[tuple[int, str]]:
    if not USE_FIREBASE:
        return []
    try:
        docs = db.collection("professores").stream()
        return [(doc.get("id"), doc.get("nome", "")) for doc in docs]
    except Exception as e:
        print(f"[get_professores_for_rateio] ERRO: {e}")
        return []
