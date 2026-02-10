# Setup Firebase + Firestore para Desenvolvimento e Deploy

Este documento explica como configurar a aplicação Flask para usar Firebase Firestore.

## 1. Desenvolvimento Local (com arquivo `serviceAccount.json`)

### Obter credenciais do Firebase

1. Acesse **Firebase Console** (https://console.firebase.google.com/)
2. Selecione seu projeto → **Configurações** (ícone de engrenagem) → **Contas de Serviço**
3. Clique em **Gerar nova chave privada** e salve o JSON

### Configurar variáveis de ambiente

Coloque o arquivo em `/workspaces/validacao-tempo/serviceAccount.json`:

```bash
# Opção 1: Via terminal
cp ~/Downloads/serviceAccount.json /workspaces/validacao-tempo/serviceAccount.json
chmod 600 /workspaces/validacao-tempo/serviceAccount.json

# Opção 2: Upload via VS Code (File Explorer → Upload Files)
```

Exporte as variáveis de ambiente:

```bash
export USE_FIREBASE=1
export FIREBASE_CREDENTIALS=/workspaces/validacao-tempo/serviceAccount.json
python app.py
```

Ou crie um arquivo `.env` local (não será commitado):

```bash
# .env (local only, não comite)
USE_FIREBASE=1
FIREBASE_CREDENTIALS=/workspaces/validacao-tempo/serviceAccount.json
```

Depois carregue e execute:

```bash
source .env
python app.py
```

### Testar inicialização

```bash
export USE_FIREBASE=1
export FIREBASE_CREDENTIALS=/workspaces/validacao-tempo/serviceAccount.json
bash scripts/setup_firebase.sh
```

---

## 2. Deploy em Produção (Vercel/Railway/Heroku)

Como o arquivo `serviceAccount.json` **não pode ser commitado**, use a variável de ambiente `FIREBASE_CREDENTIALS_JSON` com o conteúdo JSON em base64.

### Preparar credenciais para Vercel

```bash
# 1. Codifique o serviceAccount.json em base64
cat serviceAccount.json | base64 -w 0 > credentials.b64

# 2. Copie o conteúdo e coloque em variável de ambiente Vercel:
cat credentials.b64
```

### Configurar no Vercel

1. Acesse seu dashboard do Vercel → selecione o projeto
2. **Settings** → **Environment Variables**
3. Adicione as variáveis:
   - **Nome**: `USE_FIREBASE`  
     **Valor**: `1`
   - **Nome**: `FIREBASE_CREDENTIALS_JSON`  
     **Valor**: *(conteúdo base64 do comando acima)*

### Como funciona no Vercel

O `db_layer.py` automaticamente:
1. Detecta `FIREBASE_CREDENTIALS_JSON`
2. Decodifica a string base64 (se necessário)
3. Cria um arquivo temporário com as credenciais
4. Inicializa o Firebase Admin SDK

### Alternativa: Google Cloud ADC

Se você estiver usando o Vercel com Google Cloud integrado, ativar **Application Default Credentials** é mais simples:

```bash
# Vercel: Definir apenas
USE_FIREBASE=1
# O resto é automático se o projeto estiver vinculado ao Google Cloud
```

---

## 3. Variáveis de Ambiente Resumidas

| Variável | Local | Prod (Vercel) | Descrição |
|----------|-------|---------------|-----------|
| `USE_FIREBASE` | `1` | `1` | Ativa uso do Firestore |
| `FIREBASE_CREDENTIALS` | `/path/to/serviceAccount.json` | *(não use)* | Caminho do JSON (dev local) |
| `FIREBASE_CREDENTIALS_JSON` | *(não use)* | `base64_encoded_json` | JSON base64 (Vercel) |
| `SECRET_KEY` | `troque-esta-chave-em-producao` | `CHAVE_SEGURA_GERADA` | Flask secret key |
| `PORT` | *(opcional, padrão 5000)* | *(Vercel gerencia)* | Porta do servidor |

---

## 4. Vercel Function Setup (se necessário)

Se você estiver usando **Vercel Functions** (serverless), o `app.py` precisa ser exposto como handler:

Crie `api/index.py`:

```python
from app import app

def handler(request):
    return app(request)
```

E atualize `vercel.json`:

```json
{
  "public": "static",
  "buildCommand": "pip install -r requirements.txt",
  "env": {
    "USE_FIREBASE": "@firebase_enabled",
    "FIREBASE_CREDENTIALS_JSON": "@firebase_credentials"
  }
}
```

---

## 5. Checklist de Produção

- [ ] Credenciais do Firebase (`serviceAccount.json`) geradas
- [ ] Base64 das credenciais pronto
- [ ] Variáveis de ambiente configuradas no Vercel
- [ ] `requirements.txt` atualizado (firebase-admin incluído)
- [ ] `.gitignore` contém `serviceAccount.json` e `.env`
- [ ] Firestore Database criado no Firebase Console
- [ ] Regras de segurança configuradas (não deixar permissivo em prod)
- [ ] Teste local com `USE_FIREBASE=1` antes de deployer
- [ ] Deploy testado e verificado

---

## 6. Troubleshooting

**Erro: "DefaultCredentialsError"**
- Verifique se `USE_FIREBASE=1` está definido
- Verifique se `FIREBASE_CREDENTIALS_JSON` está definido e em base64 válido

**Erro: "Certificate is not valid"**
- Verifique se o JSON não foi truncado ou corrompido no base64
- Rode `echo $FIREBASE_CREDENTIALS_JSON | base64 -d` para testar decodificação

**Firestore vazio após deploy**
- Normal em uma app nova. Dados serão criados conforme você adiciona registros.
- Se migrou SQLite local, rode `python scripts/migrate_sqlite_to_firestore.py` antes de deployer.

---

## Referências

- [Firebase Admin SDK (Python)](https://firebase.google.com/docs/admin/setup)
- [Firestore Documentation](https://firebase.google.com/docs/firestore)
- [Vercel Environment Variables](https://vercel.com/docs/projects/environment-variables)
