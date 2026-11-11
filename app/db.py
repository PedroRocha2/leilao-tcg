import shutil
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import click
from flask import current_app, g

SCHEMA = Path(__file__).with_name("schema.sql")
VERSAO_DO_ESQUEMA = 4


def agora_utc() -> datetime:
    return datetime.now(UTC)


def para_texto(momento: datetime) -> str:
    return momento.astimezone(UTC).isoformat(timespec="milliseconds")


def de_texto(texto: str) -> datetime:
    return datetime.fromisoformat(texto)


def conectar(caminho: str) -> sqlite3.Connection:
    conexao = sqlite3.connect(caminho, isolation_level=None, timeout=10)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    return conexao


@contextmanager
def transacao(conexao: sqlite3.Connection, imediata: bool = False):
    if conexao.in_transaction:
        yield conexao
        return
    conexao.execute("BEGIN IMMEDIATE" if imediata else "BEGIN")
    try:
        yield conexao
    except BaseException:
        conexao.execute("ROLLBACK")
        raise
    conexao.execute("COMMIT")


def marcadores(quantidade: int) -> str:
    return ", ".join("?" * quantidade)


def obter_conexao() -> sqlite3.Connection:
    if "db" not in g:
        g.db = conectar(current_app.config["DATABASE"])
    return g.db


def fechar_conexao(_erro=None) -> None:
    conexao = g.pop("db", None)
    if conexao is not None:
        conexao.close()


def _versao(caminho: Path) -> int:
    conexao = sqlite3.connect(caminho)
    try:
        return conexao.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conexao.close()


def preparar_banco(caminho: str, recriar: bool = False, agora: datetime | None = None,
                   administrador: dict | None = None) -> None:
    """Cria o banco com a carga inicial. `administrador` traz login, senha e iteracoes da conta do lojista."""
    from app.carga_inicial import popular

    arquivo = Path(caminho)
    if arquivo.exists() and (recriar or _versao(arquivo) != VERSAO_DO_ESQUEMA):
        arquivo.unlink()
    if arquivo.exists():
        return
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    conexao = conectar(caminho)
    try:
        conexao.executescript(SCHEMA.read_text(encoding="utf-8"))
        with transacao(conexao):
            popular(conexao, agora or agora_utc(), administrador)
            conexao.execute(f"PRAGMA user_version = {VERSAO_DO_ESQUEMA}")
    finally:
        conexao.close()


def administrador_da_configuracao() -> dict:
    configuracao = current_app.config
    return {"login": configuracao["ADMIN_LOGIN"], "senha": configuracao["ADMIN_SENHA"],
            "iteracoes": configuracao["PBKDF2_ITERACOES"]}


@click.command("reiniciar-dados")
def comando_reiniciar_dados() -> None:
    preparar_banco(current_app.config["DATABASE"], recriar=True, administrador=administrador_da_configuracao())
    shutil.rmtree(current_app.config["PASTA_DE_FOTOS"], ignore_errors=True)
    click.echo("Banco recriado: leilões com prazos contados a partir de agora e nenhuma conta de cliente.")


def registrar(app) -> None:
    app.teardown_appcontext(fechar_conexao)
    app.cli.add_command(comando_reiniciar_dados)
