import shutil
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import click
from flask import current_app, g

SCHEMA = Path(__file__).with_name("schema.sql")
# schema.sql é a versão base; cada incremento também atualiza bancos existentes, sem perder dados.
VERSAO_BASE = 4
INCREMENTOS = {5: Path(__file__).with_name("schema_v5.sql"), 6: Path(__file__).with_name("schema_v6.sql")}
VERSAO_DO_ESQUEMA = max(INCREMENTOS)


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
    """`administrador`: login, senha e iteracoes da conta do lojista."""
    from app.carga_inicial import popular

    arquivo = Path(caminho)
    # Versão anterior à base ou desconhecida não tem como ser atualizada.
    if arquivo.exists() and (recriar or not VERSAO_BASE <= _versao(arquivo) <= VERSAO_DO_ESQUEMA):
        arquivo.unlink()
    novo = not arquivo.exists()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    conexao = conectar(caminho)
    try:
        if novo:
            # A versão só é marcada no fim: se a carga falhar, o banco é recriado na próxima vez.
            conexao.executescript(SCHEMA.read_text(encoding="utf-8"))
            for versao in sorted(INCREMENTOS):
                conexao.executescript(INCREMENTOS[versao].read_text(encoding="utf-8"))
            with transacao(conexao):
                popular(conexao, agora or agora_utc(), administrador)
                conexao.execute(f"PRAGMA user_version = {VERSAO_DO_ESQUEMA}")
        else:
            _atualizar_esquema(conexao)
    finally:
        conexao.close()


def _atualizar_esquema(conexao: sqlite3.Connection) -> None:
    atual = conexao.execute("PRAGMA user_version").fetchone()[0]
    for versao in sorted(versao for versao in INCREMENTOS if versao > atual):
        # Incremento, preenchimento e versão na mesma transação.
        try:
            conexao.executescript("BEGIN;\n" + INCREMENTOS[versao].read_text(encoding="utf-8"))
            if versao == 6:
                _preencher_atributos(conexao)
            conexao.execute(f"PRAGMA user_version = {versao}")
        except BaseException:
            if conexao.in_transaction:
                conexao.execute("ROLLBACK")
            raise
        conexao.execute("COMMIT")


def _preencher_atributos(conexao: sqlite3.Connection) -> None:
    """Cartas de vendedores: os atributos saem da descrição sugerida ("Tipo: Fire; Raridade: Rare.")."""
    from app.carga_inicial import ATRIBUTOS, CARTAS
    from app.catalogo import atributos_da_descricao

    da_carga = {(nome, edicao) for _, nome, edicao, *_ in CARTAS}
    cartas = conexao.execute(
        "SELECT c.id, c.nome, c.edicao, c.descricao, j.nome AS jogo FROM cartas c JOIN jogos j ON j.id = c.jogo_id"
        " WHERE c.id NOT IN (SELECT carta_id FROM carta_atributos)").fetchall()
    with transacao(conexao):
        for carta in cartas:
            if (carta["nome"], carta["edicao"]) in da_carga:
                pares = ATRIBUTOS[carta["nome"]].items()
            else:
                pares = atributos_da_descricao(carta["jogo"], carta["descricao"])
            conexao.executemany(
                "INSERT OR IGNORE INTO carta_atributos (carta_id, chave, valor) VALUES (?, ?, ?)",
                [(carta["id"], chave, valor) for chave, valor in pares])


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
