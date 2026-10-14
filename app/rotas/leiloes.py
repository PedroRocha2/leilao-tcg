"""Ver leilões ativos (RF06, RF08) e dar lance (RF07)."""

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for

from app.apresentacao import cartao, descricao_da_foto, estado, ficha, slug
from app.db import transacao
from app.dominio.dinheiro import ValorMonetarioInvalido, formatar_reais, ler_reais
from app.dominio.leiloes import LanceRecusado
from app.rotas.comum import agora, cliente_atual, quer_json, repositorios

bp = Blueprint("leiloes", __name__)


@bp.get("/")
def inicio():
    return redirect(url_for("leiloes.listar"))


@bp.get("/leiloes")
def listar():
    _, repositorio = repositorios()
    momento = agora()
    jogos = repositorio.jogos()
    filtro = request.args.get("jogo")
    jogo = next((j for j in jogos if slug(j.nome) == filtro), None) if filtro else None
    if filtro and jogo is None:
        return redirect(url_for("leiloes.listar"))

    por_jogo = repositorio.ativos_por_jogo(momento)
    chips = [{"nome": j.nome, "slug": slug(j.nome), "total": por_jogo.get(j.id, 0),
              "atual": jogo is not None and j.id == jogo.id} for j in jogos]
    leiloes = repositorio.ativos(momento, jogo.id if jogo else None)
    return render_template("leiloes.html", cartoes=[cartao(l, momento) for l in leiloes],
                           chips=chips, jogo=jogo, total_geral=sum(por_jogo.values()))


def _carregar(leilao_id: int):
    _, repositorio = repositorios()
    leilao = repositorio.por_id(leilao_id)
    if leilao is None:
        abort(404)
    return leilao, repositorio


def _pagina(leilao, repositorio, momento, status=200, erro=None, valor_digitado=None):
    fotos = [(url, descricao_da_foto(leilao, url, posicao))
             for posicao, url in enumerate(leilao.carta.fotos, start=1)]
    return render_template(
        "leilao.html",
        leilao=leilao,
        e=estado(leilao, momento, cliente_atual()),
        fotos=fotos,
        ficha=ficha(leilao, momento),
        outros=[cartao(outro, momento) for outro in repositorio.outros_do_jogo(leilao, momento)],
        jogo_slug=slug(leilao.carta.jogo.nome),
        erro=erro,
        valor_digitado=valor_digitado,
    ), status


def _json(leilao, momento) -> dict:
    """Estado do painel e as linhas da tabela já renderizadas, para atualizar sem recarregar."""
    e = estado(leilao, momento, cliente_atual())
    return {
        "estado": {chave: valor for chave, valor in e.items() if chave != "linhas"},
        "tabela": render_template("_linhas_lances.html", e=e),
    }


@bp.get("/leiloes/<int:leilao_id>")
def detalhe(leilao_id: int):
    leilao, repositorio = _carregar(leilao_id)
    return _pagina(leilao, repositorio, agora())


@bp.get("/leiloes/<int:leilao_id>/estado")
def estado_atual(leilao_id: int):
    leilao, _ = _carregar(leilao_id)
    return jsonify(_json(leilao, agora()))


def _recusar(leilao_id: int, mensagem: str, valor_digitado: str, motivo=None):
    leilao, repositorio = _carregar(leilao_id)
    momento = agora()
    if quer_json():
        return jsonify(ok=False, mensagem=mensagem, motivo=motivo, **_json(leilao, momento)), 422
    return _pagina(leilao, repositorio, momento, 422, erro=mensagem, valor_digitado=valor_digitado)


@bp.post("/leiloes/<int:leilao_id>/lances")
def dar_lance(leilao_id: int):
    """RF07. As regras são do domínio e valem aqui no servidor, venha o pedido do formulário,
    do fetch da página ou de qualquer outro cliente HTTP."""
    pagina = url_for(".detalhe", leilao_id=leilao_id)
    cliente = cliente_atual()
    if cliente is None:
        entrar = url_for("contas.entrar", proximo=pagina)
        if quer_json():
            return jsonify(ok=False, mensagem="Entre na sua conta para dar lances.", entrar=entrar), 401
        return redirect(entrar)

    texto = request.form.get("valor", "")
    clientes, repositorio = repositorios()
    momento = agora()
    try:
        valor = ler_reais(texto)
        # BEGIN IMMEDIATE: lê o maior lance e grava o novo sem outro lance no meio (RN13).
        with transacao(repositorio.conexao, imediata=True):
            leilao = repositorio.por_id(leilao_id)
            if leilao is None:
                abort(404)
            licitante = clientes.por_id(cliente.id)
            lance = licitante.darLance(leilao, valor, momento)
            repositorio.salvar_lance(leilao, lance)
    except ValorMonetarioInvalido as erro:
        return _recusar(leilao_id, str(erro), texto)
    except LanceRecusado as recusa:
        return _recusar(leilao_id, recusa.mensagem, texto, recusa.motivo)

    mensagem = f"Lance de {formatar_reais(lance.valor)} registrado. Você está liderando."
    if quer_json():
        return jsonify(ok=True, mensagem=mensagem, **_json(leilao, momento)), 201
    flash(mensagem, "sucesso")
    return redirect(pagina, code=303)
