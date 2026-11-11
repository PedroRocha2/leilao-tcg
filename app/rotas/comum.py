import hashlib
import secrets
from decimal import Decimal
from functools import wraps
from urllib.parse import urlsplit

from flask import current_app, g, redirect, render_template, request, session, url_for

from app.anuncio import PREFIXO_DAS_FOTOS
from app.apresentacao import slug
from app.db import obter_conexao
from app.dominio.contas import Administrador, Cliente, Usuario
from app.repositorios import RepositorioClientes, RepositorioLeiloes, RepositorioLoja


def repositorios() -> tuple[RepositorioClientes, RepositorioLeiloes]:
    conexao = obter_conexao()
    clientes = RepositorioClientes(conexao)
    return clientes, RepositorioLeiloes(conexao, clientes)


def loja() -> RepositorioLoja:
    return RepositorioLoja(obter_conexao())


TAMANHO_DA_BUSCA = 80


def jogos_da_loja() -> dict[str, str]:
    """Os jogos do catálogo de cartas, pelo slug. No banco só existem os que já tiveram carta cadastrada."""
    return {slug(nome): nome for nome in current_app.config["CATALOGO"].jogos}


def texto_da_busca() -> str:
    """O nome ou o código que o visitante digitou na busca do topo."""
    return " ".join(request.args.get("q", "").split())[:TAMANHO_DA_BUSCA]


def busca_do_topo() -> dict:
    """Os jogos do combobox e o que a busca do topo mostra preenchido nas páginas de leilões."""
    nas_listas = request.endpoint in ("leiloes.listar", "leiloes.jogo")
    return {"jogos": jogos_da_loja(), "tamanho": TAMANHO_DA_BUSCA,
            "jogo": (request.view_args or {}).get("slug", "") if nas_listas else "",
            "q": texto_da_busca() if nas_listas else ""}


def agora():
    """O mesmo instante durante todo o pedido: quem lê os leilões vê o que o encerramento já tratou."""
    if "agora" not in g:
        g.agora = current_app.config["RELOGIO"]()
    return g.agora


def _assinatura(usuario: Usuario) -> str:
    return hashlib.sha256(f"{usuario.id}:{usuario.email}:{usuario.senhaHash}".encode()).hexdigest()


def usuario_atual() -> Usuario | None:
    """Quem está logado: um cliente ou o administrador."""
    if "usuario" not in g:
        usuario_id = session.get("usuario_id")
        g.usuario = RepositorioClientes(obter_conexao()).usuario_por_id(usuario_id) if usuario_id else None
        valida = (g.usuario is not None and g.usuario.ativo
                  and secrets.compare_digest(session.get("assinatura", ""), _assinatura(g.usuario)))
        if usuario_id and not valida:
            session.pop("usuario_id", None)
            session.pop("assinatura", None)
            g.usuario = None
    return g.usuario


def cliente_atual() -> Cliente | None:
    usuario = usuario_atual()
    return usuario if isinstance(usuario, Cliente) else None


def administrador_atual() -> Administrador | None:
    usuario = usuario_atual()
    return usuario if isinstance(usuario, Administrador) else None


def iniciar_sessao(usuario: Usuario) -> None:
    session.clear()
    session["usuario_id"] = usuario.id
    session["assinatura"] = _assinatura(usuario)
    g.usuario = usuario


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
    partes = urlsplit(destino or "")
    if destino and destino.startswith("/") and not destino.startswith("//") and not partes.netloc:
        return destino
    return padrao


def url_da_foto(foto: str) -> str:
    """As fotos da carga inicial são arquivos estáticos; as das cartas cadastradas ficam na pasta de fotos."""
    if foto.startswith(PREFIXO_DAS_FOTOS):
        return url_for("leiloes.foto", arquivo=foto.removeprefix(PREFIXO_DAS_FOTOS))
    return url_for("static", filename=foto)


def caminho_atual() -> str:
    return request.full_path.rstrip("?") if request.query_string else request.path


def registrar_operacao(operacao: str, valor: Decimal | None = None, detalhe: str = "",
                       usuario: Usuario | None = None) -> None:
    """RF19: grava no log quem fez a operação, de qual IP e quando."""
    usuario = usuario or usuario_atual()
    loja().registrar(operacao, agora(), usuario.id if usuario else None, valor, request.remote_addr, detalhe)


def login_obrigatorio(rota):
    """Páginas do cliente. O administrador não compra nem vende: é levado para a área dele."""
    @wraps(rota)
    def protegida(*args, **kwargs):
        if administrador_atual() is not None:
            return redirect(url_for("admin.leiloes"))
        if cliente_atual() is None:
            return redirect(url_for("contas.entrar", proximo=caminho_atual()))
        return rota(*args, **kwargs)

    return protegida


def admin_obrigatorio(rota):
    """RN14 e RNF07: as funções administrativas só respondem ao administrador, conferido no servidor."""
    @wraps(rota)
    def protegida(*args, **kwargs):
        if administrador_atual() is None:
            if cliente_atual() is None:
                return redirect(url_for("contas.entrar", proximo=caminho_atual()))
            return render_template("erro.html", titulo="Área restrita ao administrador",
                                   texto="Sua conta não tem acesso às funções administrativas da loja."), 403
        return rota(*args, **kwargs)

    return protegida
