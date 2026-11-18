import hashlib
import secrets
from decimal import Decimal
from functools import wraps
from urllib.parse import urlsplit

from flask import current_app, g, redirect, render_template, request, session, url_for

from app.anuncio import PREFIXO_DAS_FOTOS
from app.apresentacao import slug
from app.correio import CorreioIndisponivel, aviso_de_pagamento
from app.db import obter_conexao
from app.dominio.contas import Administrador, Cliente, Usuario
from app.repositorios import RepositorioClientes, RepositorioLeiloes, RepositorioLoja
from app.repositorios.cobrancas import Cobranca, RepositorioCobrancas, StatusCobranca


def repositorios() -> tuple[RepositorioClientes, RepositorioLeiloes]:
    conexao = obter_conexao()
    clientes = RepositorioClientes(conexao)
    return clientes, RepositorioLeiloes(conexao, clientes)


def loja() -> RepositorioLoja:
    return RepositorioLoja(obter_conexao())


def cobrancas() -> RepositorioCobrancas:
    return RepositorioCobrancas(obter_conexao())


TAMANHO_DA_BUSCA = 80


def jogos_da_loja() -> dict[str, str]:
    """Pelo catálogo: no banco só existem os jogos que já tiveram carta cadastrada."""
    return {slug(nome): nome for nome in current_app.config["CATALOGO"].jogos}


def texto_da_busca() -> str:
    return " ".join(request.args.get("q", "").split())[:TAMANHO_DA_BUSCA]


def busca_do_topo() -> dict:
    nas_listas = request.endpoint in ("leiloes.listar", "leiloes.jogo")
    return {"jogos": jogos_da_loja(), "tamanho": TAMANHO_DA_BUSCA,
            "jogo": (request.view_args or {}).get("slug", "") if nas_listas else "",
            "q": texto_da_busca() if nas_listas else ""}


def agora():
    """O mesmo instante durante todo o pedido."""
    if "agora" not in g:
        g.agora = current_app.config["RELOGIO"]()
    return g.agora


def _assinatura(usuario: Usuario) -> str:
    return hashlib.sha256(f"{usuario.id}:{usuario.email}:{usuario.senhaHash}".encode()).hexdigest()


def usuario_atual() -> Usuario | None:
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
    """As fotos da carga inicial são arquivos estáticos."""
    if foto.startswith(PREFIXO_DAS_FOTOS):
        return url_for("leiloes.foto", arquivo=foto.removeprefix(PREFIXO_DAS_FOTOS))
    return url_for("static", filename=foto)


def caminho_atual() -> str:
    return request.full_path.rstrip("?") if request.query_string else request.path


def registrar_operacao(operacao: str, valor: Decimal | None = None, detalhe: str = "",
                       usuario: Usuario | None = None) -> None:
    """RF19: quem fez a operação, de qual IP e quando."""
    usuario = usuario or usuario_atual()
    loja().registrar(operacao, agora(), usuario.id if usuario else None, valor, request.remote_addr, detalhe)


def url_publica(endpoint: str, **valores) -> str | None:
    """None sem endereço https público: o gateway não aceita os da própria máquina."""
    base = (current_app.config.get("URL_PUBLICA") or request.url_root).rstrip("/")
    partes = urlsplit(base)
    if partes.scheme != "https" or partes.hostname in (None, "localhost", "127.0.0.1", "::1"):
        return None
    return base + url_for(endpoint, **valores)


def registrar_pagamento_no_gateway(cobranca: Cobranca, leilao, gateway) -> None:
    """RF19: no nome do comprador e sem IP (quem avisa é o gateway)."""
    comprador = leilao.transacao.comprador
    if cobranca.status == StatusCobranca.PAGA:
        operacao, valor = "pagamento de arremate", leilao.transacao.valor
    else:
        operacao, valor = "pagamento creditado na carteira", cobranca.valor
    loja().registrar(operacao, agora(), comprador.id, valor, None,
                     f"leilão {leilao.id}: {leilao.carta.nome} ({gateway.nome}, pagamento {cobranca.pagamentoId})")


def avisar_pagamento_confirmado(leilao) -> None:
    """Roda depois de gravar o pagamento: uma falha no e-mail não desfaz o pagamento."""
    assunto, texto = aviso_de_pagamento(leilao, url_publica("minha_conta.arremates"))
    try:
        current_app.config["CORREIO"].enviar(leilao.transacao.comprador.email, assunto, texto)
    except CorreioIndisponivel as falha:
        current_app.logger.warning("E-mail do código de retirada do leilão %s não enviado: %s", leilao.id, falha)


def login_obrigatorio(rota):
    """O administrador não compra nem vende: vai para a área dele."""
    @wraps(rota)
    def protegida(*args, **kwargs):
        if administrador_atual() is not None:
            return redirect(url_for("admin.leiloes"))
        if cliente_atual() is None:
            return redirect(url_for("contas.entrar", proximo=caminho_atual()))
        return rota(*args, **kwargs)

    return protegida


def admin_obrigatorio(rota):
    """RN14 e RNF07: só o administrador, conferido no servidor."""
    @wraps(rota)
    def protegida(*args, **kwargs):
        if administrador_atual() is None:
            if cliente_atual() is None:
                return redirect(url_for("contas.entrar", proximo=caminho_atual()))
            return render_template("erro.html", titulo="Área restrita ao administrador",
                                   texto="Sua conta não tem acesso às funções administrativas da loja."), 403
        return rota(*args, **kwargs)

    return protegida
