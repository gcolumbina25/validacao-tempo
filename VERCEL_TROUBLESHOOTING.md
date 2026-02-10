# 🐛 Guia de Troubleshooting - Vercel + Firebase

## ❌ Erro: "500: INTERNAL_SERVER_ERROR"

### O que mudamos para corrigir:

1. **Estrutura simplificada**: 
   - ❌ Removido: `api/index.py` (Vercel não conseguia encontrar)
   - ✅ Adicionado: `wsgi.py` (Vercel detecta automaticamente)

2. **vercel.json simplificado**:
   - ❌ Antes: Tinha `functions` e `routes` complexas
   - ✅ Agora: Apenas `buildCommand` e `env`

3. **db_layer.py corrigido**:
   - ✅ `USE_FIREBASE` volta ao padrão "0" (local)
   - ✅ `vercel.json` sobrescreve para "1" em produção
   - ✅ Logs detalhados de inicialização Firebase

## 🔧 Como Testar Localmente

### Desenvolvimento com SQLite:
```bash
# Padrão - usa SQLite via database.db
python app.py
```

### Testar Firebase localmente:
```bash
# Forçar Firebase mesmo no desenvolvimento
USE_FIREBASE=1 python app.py
```

## 📋 Checklist de Deploy Vercel

Antes de fazer push, verifique:

- [ ] `wsgi.py` existe e exporta `app`
- [ ] `vercel.json` tem `USE_FIREBASE: "1"` no env
- [ ] `FIREBASE_CREDENTIALS_JSON` está em `vercel.json`
- [ ] `requirements.txt` inclui `firebase-admin==6.1.0`
- [ ] `db_layer.py` tem `USE_FIREBASE = os.environ.get("USE_FIREBASE", "0") == "1"`
- [ ] Pasta `api/` foi removida

## 📊 Arquivos Importantes

| Arquivo | Propósito | Status |
|---------|-----------|--------|
| [wsgi.py](wsgi.py) | Entry point para Vercel | ✅ Novo |
| [vercel.json](vercel.json) | Configuração Vercel | ✅ Simplificado |
| [db_layer.py](db_layer.py) | Suporte Firebase | ✅ Atualizado |
| [app.py](app.py) | Aplicação Flask | ✅ Sem mudanças |
| Procfile | ❌ Desativado (era Render) | ⚠️ Ignorado |

## 🔑 Variáveis de Ambiente no Vercel

Seu `vercel.json` já tem:

```json
"env": {
  "PYTHONUNBUFFERED": "1",
  "USE_FIREBASE": "1",
  "FIREBASE_CREDENTIALS_JSON": "eyJ0eXBlIjog..."
}
```

✅ **Nada mais precisa ser configurado no dashboard do Vercel**

## 🚀 Próximas Ações

1. Verificar os logs no Vercel após novo deploy:
   ```
   Vercel Dashboard → Projeto → Deployments → Selecionar último → Ver Logs
   ```

2. Procurar por estas linhas nos logs:
   ```
   [Firebase] Credenciais decodificadas de base64
   [Firebase] Aplicativo inicializado com sucesso
   [Firebase] Cliente Firestore criado com sucesso
   ```

3. Se tiver erro, procure por:
   ```
   [Firebase] Erro ao decodificar FIREBASE_CREDENTIALS_JSON
   ```

## 💡 Dicas Importantes

### Não esqueça:
- Fazer commit de `wsgi.py` e `vercel.json`
- Verificar que `api/` foi removido pode não ter sido comitado

### Dados:
- Seu dados do **Render (SQLite) NÃO sincronizam automaticamente** com Vercel (Firebase)
- Você precisa migrar manualmente se necessário

### Desenvolvimento:
- `USE_FIREBASE=0 python app.py` → SQLite local
- `python app.py` → Padrão SQLite local
- Vercel sempre usa Firebase (sobrescrito pelo vercel.json)

## ✅ Será que funcionou?

Acesse: `https://seu-dominio-vercel.vercel.app/`

Vá para **Network** (F12) e procure por:
- Status: 200 (não 500)
- Response headers incluem `x-powered-by: Express` ou `x-vercel-*`

---

**Dúvidas?** Verifique os logs do Vercel primeiro!
