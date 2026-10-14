"""Peças usadas por todas as rotas: usuário da sessão, relógio, CSRF e redirecionamento seguro."""

import hashlib
import secrets
from functools import wraps
from urllib.parse import urlsplit

from flask import current_app, g, redirect, request, session, url_for

from app.db import obter_conexao
from app.dominio.contas import Cliente
from app.repositorios import RepositorioClientes, RepositorioLeiloes


def repositorios() -> tuple[RepositorioClientes, RepositorioLeiloes]:
    conexao = obter_conexao()
    clientes = RepositorioClientes(conexao)
    return clientes, RepositorioLeiloes(conexao, clientes)


def agora():
    return current_app.config["RELOGIO"]()


def _assinatura(cliente: Cliente) -> str:
    """Amarra a sessão à conta, não só ao id: se o banco for recriado (ou a senha mudar), um cookie
    antigo com o mesmo id não passa a valer para outra pessoa."""
    return hashlib.sha256(f"{cliente.id}:{cliente.email}:{cliente.senhaHash}".encode()).hexdigest()


def cliente_atual() -> Cliente | None:
    """O Cliente da sessão, lido uma vez por requisição."""
    if "cliente" not in g:
        cliente_id = session.get("usuario_id")
        g.cliente = RepositorioClientes(obter_conexao()).por_id(cliente_id) if cliente_id else None
        valida = (g.cliente is not None and g.cliente.ativo
                  and secrets.compare_digest(session.get("assinatura", ""), _assinatura(g.cliente)))
        if cliente_id and not valida:
            session.pop("usuario_id", None)
            session.pop("assinatura", None)
            g.cliente = None
    return g.cliente


def iniciar_sessao(cliente: Cliente) -> None:
    """Sessão nova a cada login: nada da sessão anterior (nem o token CSRF) é reaproveitado."""
    session.clear()
    session["usuario_id"] = cliente.id
    session["assinatura"] = _assinatura(cliente)
    g.cliente = cliente


def token_csrf() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def csrf_valido() -> bool:
    enviado = request.form.get("csrf_token", "")
    return bool(enviado) and secrets.compare_digest(enviado, session.get("csrf", ""))


def quer_json() -> bool:
    return request.accept_mimetypes.best == "application/json"


def destino_seguro(destino: str | None, padrao: str) -> str:
    """Só caminhos internos ("/leiloes/3"); nada de "https://outro.site" nem "//outro.site"."""
    partes = urlsplit(destino or "")
    if destino and destino.startswith("/") and not destino.startswith("//") and not partes.netloc:
        return destino
    return padrao


def caminho_atual() -> str:
    return request.full_path.rstrip("?") if request.query_string else request.path


def login_obrigatorio(rota):
    @wraps(rota)
    def protegida(*args, **kwargs):
        if cliente_atual() is None:
            return redirect(url_for("contas.entrar", proximo=caminho_atual()))
        return rota(*args, **kwargs)

    return protegida
