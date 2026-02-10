# Cadastro e Cálculo dos Meses Trabalhados - FUNDEF Terra Nova-PE

Aplicação web em Python/Flask para cadastro de professores, cálculo de meses trabalhados no período do FUNDEF e rateio proporcional de valores.

## Requisitos
- Python 3.10+

## Executar localmente
1. Criar e ativar ambiente virtual:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
2. Instalar dependências:
   ```powershell
   py -m pip install -r requirements.txt
   ```
3. Definir chave de sessão (recomendado):
   ```powershell
   $env:SECRET_KEY = "troque-por-uma-chave-forte"
   ```
4. Executar:
   ```powershell
   py app.py
   ```
5. Abrir no navegador:
   - http://127.0.0.1:5000

## Deploy no Render
Este projeto já está pronto para deploy via `render.yaml`.

1. Suba o projeto no GitHub.
2. No Render, escolha `New +` -> `Blueprint` e selecione o repositório.
3. O Render vai ler `render.yaml` e criar:
   - serviço web Python;
   - start command com `gunicorn`;
   - `SECRET_KEY` gerada automaticamente;
   - disco persistente em `/var/data` para o SQLite.
4. Após o deploy, acesse a URL pública do serviço.

## Variáveis de ambiente
- `SECRET_KEY`: chave de sessão do Flask.
- `DATA_DIR`: diretório para persistência do banco (`/var/data` no Render).
- `PORT`: porta de execução (gerenciada automaticamente no Render).
- `FLASK_DEBUG`: use `1` apenas em ambiente local.
- `USE_FIREBASE`: defina como `1` para usar Firestore (padrão: `0` usa SQLite).
- `FIREBASE_CREDENTIALS`: caminho do `serviceAccount.json` (desenvolvimento local).
- `FIREBASE_CREDENTIALS_JSON`: JSON base64 do `serviceAccount.json` (Vercel/produção).

## Firebase + Firestore

Por padrão, a aplicação usa **SQLite** local. Para usar **Firebase Firestore**:

### Desenvolvimento local
1. Obtenha `serviceAccount.json` do Firebase Console (Configurações → Contas de Serviço)
2. Coloque em `/serviceAccount.json` na raiz do projeto
3. Exporte variáveis:
   ```bash
   export USE_FIREBASE=1
   export FIREBASE_CREDENTIALS=/workspaces/validacao-tempo/serviceAccount.json
   python app.py
   ```

### Deploy em Vercel / Produção
1. Gere credenciais em base64:
   ```bash
   python scripts/encode_firebase_credentials.py
   ```
2. Copie o valor gerado
3. Em Vercel Dashboard → Project Settings → Environment Variables, adicione:
   - `USE_FIREBASE` = `1`
   - `FIREBASE_CREDENTIALS_JSON` = *(valor base64)*

Veja [SETUP_FIREBASE.md](SETUP_FIREBASE.md) para instruções detalhadas.


## Funcionalidades
- Cadastro de professores com validação de dados
- Cálculo dos meses trabalhados (1 a 120)
- Edição e exclusão de cadastro
- Rascunho de cadastro
- Validação de CPF e bloqueio de CPF duplicado
- Cálculo de rateio proporcional por meses trabalhados
- Exportação em CSV e Excel
- Persistência em SQLite (`dados/fundef.db` localmente)

## Campos coletados
- Dados pessoais (nome, CPF, RG, telefone, e-mail, endereço)
- Dados funcionais (matrícula, escola, cargo, data de admissão)
- Situação do servidor (ativo, aposentado, falecido ou sem vínculo)
- Dados bancários (banco, agência, conta, tipo de conta)
- Data inicial e data final do FUNDEF
- Quantidade de meses trabalhados calculada automaticamente

## Observações importantes
- Em produção, não use a chave padrão; configure `SECRET_KEY`.
- Se houver crescimento de tráfego e concorrência, considere migrar de SQLite para PostgreSQL.
