from __future__ import annotations

import csv
import io
import json
import os
import re
import socket
import sqlite3
import sys
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
from datetime import date, datetime
from pathlib import Path

from flask import Flask, Response, flash, redirect, render_template, request, url_for
from openpyxl import Workbook

# In executables (PyInstaller), persist files beside the .exe.
BASE_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
DATA_DIR = Path(os.environ["DATA_DIR"]).resolve() if os.environ.get("DATA_DIR") else BASE_DIR / "dados"
DATABASE_PATH = DATA_DIR / "fundef.db"
FUNDEF_DATA_INICIAL = date(1997, 1, 1)
FUNDEF_DATA_FINAL = date(2006, 12, 31)
CARGA_HORARIA_SEMANAL_FIXA = 20
VALOR_PADRAO_PRECATORIO = "5.632.494,99"
ESCOLA_OPCOES = {
    "escola": "Escola",
    "seduc": "Seduc",
}
SITUACAO_SERVIDOR_OPCOES = {
    "ativo": "Ativo",
    "aposentado": "Aposentado",
    "falecido": "Falecido",
    "sem vínculo": "Sem vínculo",
    "sem vinculo": "Sem vínculo",
}

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao")

EXPORT_COLUMNS = [
    "id",
    "nome",
    "cpf",
    "rg",
    "matricula",
    "escola",
    "cargo",
    "situacao_servidor",
    "data_admissao",
    "telefone",
    "email",
    "endereco",
    "banco",
    "agencia",
    "conta",
    "tipo_conta",
    "data_inicio_fundef",
    "data_fim_fundef",
    "carga_horaria",
    "quantidade_meses_trabalhados",
    "criado_em",
]

FORM_FIELDS = [
    "nome",
    "cpf",
    "rg",
    "matricula",
    "escola",
    "cargo",
    "situacao_servidor",
    "data_admissao",
    "telefone",
    "email",
    "endereco",
    "banco",
    "agencia",
    "conta",
    "tipo_conta",
    "data_inicio_fundef",
    "data_fim_fundef",
    "carga_horaria",
    "aceitou_declaracao",
]

# camada de dados (SQLite por padrão, Firestore se USE_FIREBASE=1)
from db_layer import (
    USE_FIREBASE,
    init_db as db_init,
    list_professores as db_list_professores,
    list_rascunhos as db_list_rascunhos,
    find_professor_by_cpf as db_find_professor_by_cpf,
    get_professor as db_get_professor,
    insert_professor as db_insert_professor,
    update_professor as db_update_professor,
    delete_professor as db_delete_professor,
    save_rascunho as db_save_rascunho,
    carregar_rascunho as db_carregar_rascunho,
    remover_rascunho as db_remover_rascunho,
    export_professores as db_export_professores,
    get_professores_for_rateio as db_professores_rateio,
)


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as conn:
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

        colunas = {
            linha["name"]
            for linha in conn.execute("PRAGMA table_info(professores)").fetchall()
        }
        if "quantidade_meses_trabalhados" not in colunas:
            conn.execute(
                """
                ALTER TABLE professores
                ADD COLUMN quantidade_meses_trabalhados INTEGER NOT NULL DEFAULT 1
                """
            )

        if "data_inicio_fundef" not in colunas:
            conn.execute("ALTER TABLE professores ADD COLUMN data_inicio_fundef TEXT")
            if "ano_inicio_fundef" in colunas:
                conn.execute(
                    """
                    UPDATE professores
                    SET data_inicio_fundef = printf('%04d-01-01', ano_inicio_fundef)
                    WHERE data_inicio_fundef IS NULL OR data_inicio_fundef = ''
                    """
                )

        if "data_fim_fundef" not in colunas:
            conn.execute("ALTER TABLE professores ADD COLUMN data_fim_fundef TEXT")
            if "ano_fim_fundef" in colunas:
                conn.execute(
                    """
                    UPDATE professores
                    SET data_fim_fundef = printf('%04d-12-31', ano_fim_fundef)
                    WHERE data_fim_fundef IS NULL OR data_fim_fundef = ''
                    """
                )

        if "situacao_servidor" not in colunas:
            conn.execute("ALTER TABLE professores ADD COLUMN situacao_servidor TEXT")
            conn.execute(
                """
                UPDATE professores
                SET situacao_servidor = 'Ativo'
                WHERE situacao_servidor IS NULL OR situacao_servidor = ''
                """
            )

        conn.execute(
            """
            UPDATE professores
            SET carga_horaria = ?
            WHERE carga_horaria IS NULL OR carga_horaria <> ?
            """,
            (CARGA_HORARIA_SEMANAL_FIXA, CARGA_HORARIA_SEMANAL_FIXA),
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


def get_table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    return {linha["name"] for linha in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def cpf_valido(cpf: str) -> bool:
    cpf = only_digits(cpf)
    if len(cpf) != 11:
        return False
    if cpf == cpf[0] * 11:
        return False

    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digito_1 = (soma * 10 % 11) % 10
    if digito_1 != int(cpf[9]):
        return False

    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digito_2 = (soma * 10 % 11) % 10
    return digito_2 == int(cpf[10])


def calcular_meses_trabalhados(data_inicio: date, data_fim: date) -> int:
    return (data_fim.year - data_inicio.year) * 12 + (data_fim.month - data_inicio.month) + 1


def normalizar_escola(value: str) -> str:
    texto = (value or "").strip()
    return ESCOLA_OPCOES.get(texto.lower(), texto)


def normalizar_situacao_servidor(value: str) -> str:
    texto = (value or "").strip()
    return SITUACAO_SERVIDOR_OPCOES.get(texto.lower(), texto)


def parse_decimal_input(value: str) -> Decimal:
    texto = (value or "").strip().replace("R$", "").replace(" ", "")
    if not texto:
        raise ValueError("O valor total do precatório é obrigatório.")

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        numero = Decimal(texto)
    except InvalidOperation as exc:
        raise ValueError("Valor monetário inválido.") from exc

    if numero <= 0:
        raise ValueError("O valor total do precatório deve ser maior que zero.")
    return numero


def distribuir_rateio(valor_total_rateio: Decimal, pesos: list[Decimal]) -> list[Decimal]:
    if not pesos:
        raise ValueError("Não há pesos para rateio.")

    total_pesos = sum(pesos)
    if total_pesos <= 0:
        raise ValueError("A soma dos pesos deve ser maior que zero.")

    total_centavos = int(
        (valor_total_rateio * Decimal("100")).to_integral_value(rounding=ROUND_DOWN)
    )
    centavos_base: list[int] = []
    restos: list[tuple[Decimal, int]] = []

    for indice, peso in enumerate(pesos):
        bruto_centavos = (valor_total_rateio * Decimal("100") * peso) / total_pesos
        parte_inteira = int(bruto_centavos.to_integral_value(rounding=ROUND_DOWN))
        centavos_base.append(parte_inteira)
        restos.append((bruto_centavos - Decimal(parte_inteira), indice))

    centavos_restantes = total_centavos - sum(centavos_base)
    restos_ordenados = sorted(restos, key=lambda item: item[0], reverse=True)
    for i in range(centavos_restantes):
        indice = restos_ordenados[i][1]
        centavos_base[indice] += 1

    return [Decimal(valor) / Decimal("100") for valor in centavos_base]


@app.template_filter("moeda_br")
def formatar_moeda_br(valor: object) -> str:
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        numero = Decimal("0")

    numero = numero.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sinal = "-" if numero < 0 else ""
    numero = abs(numero)

    inteiro, decimal = f"{numero:.2f}".split(".")
    inteiro_formatado = f"{int(inteiro):,}".replace(",", ".")
    return f"{sinal}R$ {inteiro_formatado},{decimal}"


def validar_dados(form: dict[str, str]) -> tuple[list[str], int | None]:
    erros: list[str] = []
    meses_calculados: int | None = None

    obrigatorios = {
        "nome": "Nome completo",
        "cpf": "CPF",
        "escola": "Local de Trabalho",
        "cargo": "Cargo",
        "situacao_servidor": "Situação do servidor",
        "data_admissao": "Data de admissão",
        "endereco": "Endereço",
        "banco": "Banco",
        "agencia": "Agência",
        "conta": "Conta",
        "tipo_conta": "Tipo de conta",
        "data_inicio_fundef": "Data inicial FUNDEF",
        "data_fim_fundef": "Data final FUNDEF",
        "carga_horaria": "Carga horária",
    }

    for campo, nome_legivel in obrigatorios.items():
        if not form.get(campo, "").strip():
            erros.append(f"{nome_legivel} é obrigatório.")

    cpf = form.get("cpf", "")
    if cpf and not cpf_valido(cpf):
        erros.append("CPF inválido.")

    escola = normalizar_escola(form.get("escola", ""))
    if escola and escola not in ESCOLA_OPCOES.values():
        erros.append('O campo Local de Trabalho deve ser "Escola" ou "Seduc".')

    situacao_servidor = normalizar_situacao_servidor(form.get("situacao_servidor", ""))
    if situacao_servidor and situacao_servidor not in SITUACAO_SERVIDOR_OPCOES.values():
        erros.append(
            'A situação do servidor deve ser "Ativo", "Aposentado", "Falecido" ou "Sem vínculo".'
        )

    telefone = only_digits(form.get("telefone", ""))
    if telefone and len(telefone) not in (10, 11):
        erros.append("Telefone deve ter 10 ou 11 dígitos.")

    email = form.get("email", "").strip()
    if email and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        erros.append("E-mail inválido.")

    data_inicio = form.get("data_inicio_fundef", "")
    data_fim = form.get("data_fim_fundef", "")
    try:
        data_inicio_dt = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        data_fim_dt = datetime.strptime(data_fim, "%Y-%m-%d").date()
        if data_inicio_dt > data_fim_dt:
            erros.append("A data inicial do FUNDEF não pode ser maior que a data final.")
        else:
            if data_inicio_dt < FUNDEF_DATA_INICIAL or data_fim_dt > FUNDEF_DATA_FINAL:
                erros.append(
                    "As datas do FUNDEF devem estar entre 01/01/1997 e 31/12/2006 "
                    "(período de vigência)."
                )
            else:
                meses_calculados = calcular_meses_trabalhados(data_inicio_dt, data_fim_dt)
                if meses_calculados < 1 or meses_calculados > 120:
                    erros.append(
                        "O período informado deve resultar em quantidade de meses entre 1 e 120."
                    )
    except ValueError:
        erros.append("As datas do FUNDEF devem estar em formato válido.")

    try:
        carga = int(form.get("carga_horaria", "0"))
        if carga != CARGA_HORARIA_SEMANAL_FIXA:
            erros.append(
                "A carga horária do período do FUNDEF é fixa em 20 horas semanais."
            )
    except ValueError:
        erros.append("A carga horária deve ser numérica.")

    if form.get("aceitou_declaracao") != "on":
        erros.append("É necessário aceitar a declaração de veracidade.")

    return erros, meses_calculados


def coletar_dados_formulario(form: dict[str, str]) -> dict[str, str]:
    dados: dict[str, str] = {}
    for campo in FORM_FIELDS:
        if campo == "aceitou_declaracao":
            dados[campo] = "on" if form.get(campo) == "on" else ""
            continue
        dados[campo] = form.get(campo, "").strip()
    return dados


def normalizar_dados_formulario(dados: dict[str, str]) -> dict[str, str]:
    dados_normalizados = dict(dados)
    dados_normalizados["escola"] = normalizar_escola(dados_normalizados.get("escola", ""))
    dados_normalizados["situacao_servidor"] = normalizar_situacao_servidor(
        dados_normalizados.get("situacao_servidor", "")
    )
    dados_normalizados["carga_horaria"] = str(CARGA_HORARIA_SEMANAL_FIXA)
    dados_normalizados["cpf"] = only_digits(dados_normalizados.get("cpf", ""))
    return dados_normalizados


def tentar_calcular_meses_validos(dados: dict[str, str]) -> int | None:
    data_inicio = dados.get("data_inicio_fundef", "")
    data_fim = dados.get("data_fim_fundef", "")
    if not data_inicio or not data_fim:
        return None

    try:
        data_inicio_dt = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        data_fim_dt = datetime.strptime(data_fim, "%Y-%m-%d").date()
    except ValueError:
        return None

    if data_inicio_dt > data_fim_dt:
        return None
    if data_inicio_dt < FUNDEF_DATA_INICIAL or data_fim_dt > FUNDEF_DATA_FINAL:
        return None

    meses = calcular_meses_trabalhados(data_inicio_dt, data_fim_dt)
    if meses < 1 or meses > 120:
        return None
    return meses


def salvar_rascunho_cadastro(dados: dict[str, str], rascunho_id: int | None = None) -> int:
    payload = {campo: dados.get(campo, "") for campo in FORM_FIELDS}
    payload["carga_horaria"] = str(CARGA_HORARIA_SEMANAL_FIXA)
    # usa camada de dados (Firestore ou SQLite)
    return db_save_rascunho(payload, rascunho_id)


def carregar_rascunho_cadastro(rascunho_id: int) -> dict[str, object] | None:
    r = db_carregar_rascunho(rascunho_id)
    if not r:
        return None

    payload = r.get("dados") if isinstance(r.get("dados"), dict) else r.get("dados", {})
    dados: dict[str, str] = {}
    for campo in FORM_FIELDS:
        valor = payload.get(campo, "")
        if campo == "aceitou_declaracao":
            texto_valor = str(valor).strip().lower()
            dados[campo] = "on" if texto_valor in {"on", "1", "true", "sim"} else ""
            continue
        dados[campo] = str(valor).strip() if valor is not None else ""

    dados["carga_horaria"] = str(CARGA_HORARIA_SEMANAL_FIXA)
    return {"id": r.get("id"), "dados": dados, "criado_em": r.get("criado_em"), "atualizado_em": r.get("atualizado_em")}


def remover_rascunho(rascunho_id: int) -> None:
    return db_remover_rascunho(rascunho_id)


# Initialize DB only if not using Firestore and not in read-only environment
# Skip initialization for Vercel read-only filesystem (use Firestore instead)
if not USE_FIREBASE:
    try:
        db_init()
    except (OSError, IOError):
        pass  # Ignore if filesystem is read-only (Vercel) or no permission


@app.route("/")
def index() -> str:
    if USE_FIREBASE:
        professores = db_list_professores()
        rascunhos = db_list_rascunhos()
    else:
        with get_connection() as conn:
            professores = conn.execute(
                """
                SELECT id, nome, cpf, escola, cargo, situacao_servidor, telefone, email, criado_em
                FROM professores
                ORDER BY id DESC
                """
            ).fetchall()
            rascunhos = conn.execute(
                """
                SELECT id, nome_referencia, cpf, atualizado_em, criado_em
                FROM rascunhos_professores
                ORDER BY datetime(atualizado_em) DESC, id DESC
                """
            ).fetchall()
    return render_template("index.html", professores=professores, rascunhos=rascunhos)


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro() -> str:
    if request.method == "POST":
        acao = request.form.get("acao", "salvar_cadastro")
        rascunho_id = request.form.get("rascunho_id", type=int)
        dados = coletar_dados_formulario(request.form)
        dados = normalizar_dados_formulario(dados)

        if acao == "salvar_rascunho":
            meses_rascunho = tentar_calcular_meses_validos(dados)
            if meses_rascunho is not None:
                dados["quantidade_meses_trabalhados"] = str(meses_rascunho)
            rascunho_salvo_id = salvar_rascunho_cadastro(dados, rascunho_id)
            flash("Alterações salvas em rascunho. Você pode concluir depois.", "sucesso")
            return redirect(url_for("cadastro", rascunho_id=rascunho_salvo_id))

        erros, meses_calculados = validar_dados(dados)
        cpf_limpo = dados.get("cpf", "")
        if meses_calculados is not None:
            dados["quantidade_meses_trabalhados"] = str(meses_calculados)

        if not erros:
            existente = db_find_professor_by_cpf(cpf_limpo)
            if existente:
                erros.append("Já existe um cadastro com este CPF.")

        if meses_calculados is None and not erros:
            erros.append("Não foi possível calcular a quantidade de meses trabalhados.")

        if erros:
            for erro in erros:
                flash(erro, "erro")
            return render_template(
                "cadastro.html",
                dados=dados,
                modo="novo",
                professor_id=None,
                rascunho_id=rascunho_id,
                rascunho_atualizado_em=None,
            )

        # insere via camada de dados
        payload = dict(dados)
        payload["telefone"] = only_digits(payload.get("telefone", ""))
        payload["quantidade_meses_trabalhados"] = int(meses_calculados or 0)
        payload["aceitou_declaracao"] = 1
        payload["criado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_insert_professor(payload)

        flash("Cadastro realizado com sucesso.", "sucesso")
        if rascunho_id is not None:
            db_remover_rascunho(rascunho_id)
        return redirect(url_for("index"))

    rascunho_id = request.args.get("rascunho_id", type=int)
    if rascunho_id is not None:
        rascunho = carregar_rascunho_cadastro(rascunho_id)
        if not rascunho:
            flash("Rascunho não encontrado.", "erro")
            return redirect(url_for("cadastro"))

        dados = dict(rascunho["dados"])
        meses_rascunho = tentar_calcular_meses_validos(dados)
        if meses_rascunho is not None:
            dados["quantidade_meses_trabalhados"] = str(meses_rascunho)
        return render_template(
            "cadastro.html",
            dados=dados,
            modo="novo",
            professor_id=None,
            rascunho_id=rascunho_id,
            rascunho_atualizado_em=rascunho["atualizado_em"],
        )

    return render_template(
        "cadastro.html",
        dados={"carga_horaria": str(CARGA_HORARIA_SEMANAL_FIXA)},
        modo="novo",
        professor_id=None,
        rascunho_id=None,
        rascunho_atualizado_em=None,
    )


@app.route("/editar/<int:professor_id>", methods=["GET", "POST"])
def editar(professor_id: int) -> str:
    if USE_FIREBASE:
        professor = db_get_professor(professor_id)
    else:
        with get_connection() as conn:
            professor = conn.execute(
                "SELECT * FROM professores WHERE id = ?", (professor_id,)
            ).fetchone()

    if not professor:
        flash("Cadastro não encontrado.", "erro")
        return redirect(url_for("index"))

    if request.method == "POST":
        dados = {campo: request.form.get(campo, "").strip() for campo in request.form.keys()}
        dados["escola"] = normalizar_escola(dados.get("escola", ""))
        dados["situacao_servidor"] = normalizar_situacao_servidor(
            dados.get("situacao_servidor", "")
        )
        dados["carga_horaria"] = str(CARGA_HORARIA_SEMANAL_FIXA)
        erros, meses_calculados = validar_dados(dados)

        cpf_limpo = only_digits(dados.get("cpf", ""))
        dados["cpf"] = cpf_limpo
        if meses_calculados is not None:
            dados["quantidade_meses_trabalhados"] = str(meses_calculados)

        if not erros:
            existente = db_find_professor_by_cpf(cpf_limpo)
            if existente and int(existente.get("id", 0)) != int(professor_id):
                erros.append("Já existe um cadastro com este CPF.")

        if meses_calculados is None and not erros:
            erros.append("Não foi possível calcular a quantidade de meses trabalhados.")

        if erros:
            for erro in erros:
                flash(erro, "erro")
            return render_template(
                "cadastro.html",
                dados=dados,
                modo="editar",
                professor_id=professor_id,
            )

        payload = dict(dados)
        payload["telefone"] = only_digits(payload.get("telefone", ""))
        payload["quantidade_meses_trabalhados"] = int(meses_calculados or 0)
        payload["aceitou_declaracao"] = 1
        db_update_professor(professor_id, payload)

        flash("Cadastro atualizado com sucesso.", "sucesso")
        return redirect(url_for("index"))

    dados = dict(professor)
    dados["aceitou_declaracao"] = bool(dados.get("aceitou_declaracao"))
    dados["situacao_servidor"] = normalizar_situacao_servidor(
        dados.get("situacao_servidor", "")
    ) or "Ativo"
    dados["carga_horaria"] = str(CARGA_HORARIA_SEMANAL_FIXA)
    return render_template(
        "cadastro.html",
        dados=dados,
        modo="editar",
        professor_id=professor_id,
    )


@app.route("/deletar/<int:professor_id>", methods=["POST"])
def deletar(professor_id: int) -> str:
    existente = db_get_professor(professor_id)
    if not existente:
        flash("Cadastro não encontrado.", "erro")
        return redirect(url_for("index"))
    db_delete_professor(professor_id)

    flash("Cadastro excluído com sucesso.", "sucesso")
    return redirect(url_for("index"))


@app.route("/rascunho/<int:rascunho_id>/deletar", methods=["POST"])
def deletar_rascunho(rascunho_id: int) -> str:
    existente = db_carregar_rascunho(rascunho_id)
    if not existente:
        flash("Rascunho não encontrado.", "erro")
        return redirect(url_for("index"))
    db_remover_rascunho(rascunho_id)

    flash("Rascunho excluído com sucesso.", "sucesso")
    return redirect(url_for("index"))


@app.route("/healthz")
def healthz() -> tuple[str, int]:
    return "ok", 200


@app.route("/exportar-csv")
def exportar_csv() -> Response:
    registros = db_export_professores()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(EXPORT_COLUMNS)

    for r in registros:
        writer.writerow([r[coluna] for coluna in r.keys()])

    nome_arquivo = f"cadastros-fundef-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )


@app.route("/exportar-excel")
def exportar_excel() -> Response:
    registros = db_export_professores()

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Cadastros"
    sheet.append(EXPORT_COLUMNS)

    for registro in registros:
        sheet.append([registro[coluna] for coluna in EXPORT_COLUMNS])

    output = io.BytesIO()
    workbook.save(output)
    output.seek(0)

    nome_arquivo = f"cadastros-fundef-{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
    return Response(
        output.getvalue(),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )


@app.route("/rateio", methods=["GET", "POST"])
def rateio() -> str:
    professores = db_professores_rateio()

    dados_form = {
        "valor_total": VALOR_PADRAO_PRECATORIO,
    }
    resultado_rateio: list[dict[str, object]] | None = None
    resumo_rateio: dict[str, object] | None = None

    if request.method == "POST":
        dados_form = {
            "valor_total": request.form.get("valor_total", "").strip(),
        }
        erros: list[str] = []

        if not professores:
            erros.append("Não há cadastros para calcular o rateio.")

        valor_total = Decimal("0")

        try:
            valor_total = parse_decimal_input(dados_form["valor_total"])
        except ValueError as exc:
            erros.append(str(exc))

        if erros:
            for erro in erros:
                flash(erro, "erro")
            return render_template(
                "rateio.html",
                dados_form=dados_form,
                resultado_rateio=resultado_rateio,
                resumo_rateio=resumo_rateio,
                quantidade_professores=len(professores),
            )

        valor_disponivel_rateio = valor_total.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        base_rateio: list[dict[str, object]] = []
        pesos: list[Decimal] = []
        for professor in professores:
            meses = int(professor["quantidade_meses_trabalhados"] or 0)
            peso = Decimal(meses)

            base_rateio.append(
                {
                    "id": professor["id"],
                    "nome": professor["nome"],
                    "cpf": professor["cpf"],
                    "escola": professor["escola"],
                    "cargo": professor["cargo"],
                    "situacao_servidor": professor["situacao_servidor"],
                    "meses": meses,
                    "peso": peso,
                }
            )
            pesos.append(peso)

        try:
            valores_rateio = distribuir_rateio(valor_disponivel_rateio, pesos)
        except ValueError as exc:
            flash(str(exc), "erro")
            return render_template(
                "rateio.html",
                dados_form=dados_form,
                resultado_rateio=resultado_rateio,
                resumo_rateio=resumo_rateio,
                quantidade_professores=len(professores),
            )

        resultado_rateio = []
        for item, valor_rateio in zip(base_rateio, valores_rateio):
            resultado_rateio.append(
                {
                    **item,
                    "valor_rateio": valor_rateio,
                }
            )

        soma_pesos = sum(pesos)
        resumo_rateio = {
            "criterio_texto": "Meses trabalhados",
            "quantidade_professores": len(professores),
            "valor_total": valor_total,
            "valor_disponivel_rateio": valor_disponivel_rateio,
            "soma_pesos": soma_pesos,
        }
        flash("Rateio calculado com sucesso.", "sucesso")

    return render_template(
        "rateio.html",
        dados_form=dados_form,
        resultado_rateio=resultado_rateio,
        resumo_rateio=resumo_rateio,
        quantidade_professores=len(professores),
    )


if __name__ == "__main__":
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip_rede = s.getsockname()[0]
    except OSError:
        ip_rede = "127.0.0.1"

    print(f"Servidor local: http://127.0.0.1:{port}", flush=True)
    print(f"Servidor na rede: http://{ip_rede}:{port}", flush=True)
    app.run(debug=debug, host=host, port=port)
