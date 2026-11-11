from pathlib import Path

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request,
                   send_from_directory, url_for)

from app.apresentacao import cartao, descricao_da_foto, estado, ficha, slug as slug_de
from app.db import transacao
from app.dominio.dinheiro import ValorMonetarioInvalido, formatar_reais, ler_reais
from app.dominio.leiloes import LanceRecusado, StatusLeilao
from app.rotas.comum import (administrador_atual, agora, cliente_atual, jogos_da_loja, quer_json,
                             registrar_operacao, repositorios, texto_da_busca)

bp = Blueprint("leiloes", __name__)

# O painel de filtros de cada jogo: slug do jogo -> template incluído na página dele (jogo.html).
# Ainda não há nenhum; para dar filtros a um jogo, crie o template e registre aqui.
FILTROS_POR_JOGO: dict[str, str] = {}
PASTA_DAS_CAPAS = "img/jogos"


@bp.get("/")
def inicio():
    """A página inicial: a apresentação da loja, os jogos e, abaixo, todos os leilões ativos."""
    _, repositorio = repositorios()
    momento = agora()
    ids = {jogo.nome: jogo.id for jogo in repositorio.jogos()}
    por_jogo = repositorio.ativos_por_jogo(momento)
    jogos = [{"slug": s, "nome": nome, "total": por_jogo.get(ids.get(nome), 0), "capa": _capa(s)}
             for s, nome in jogos_da_loja().items()]
    return render_template("inicio.html", jogos=jogos,
                           cartoes=[cartao(leilao, momento) for leilao in repositorio.ativos(momento)])


def _capa(slug_do_jogo: str) -> str | None:
    """A imagem do jogo na página inicial, quando existe uma em static/img/jogos."""
    arquivo = f"{PASTA_DAS_CAPAS}/{slug_do_jogo}.webp"
    return arquivo if (Path(current_app.static_folder) / arquivo).is_file() else None


@bp.get("/leiloes")
def listar():
    """Os leilões ativos de todos os jogos, ou os que a busca do topo acha pelo nome ou pelo código."""
    filtro, texto = request.args.get("jogo"), texto_da_busca()
    if filtro:
        # O jogo escolhido no combobox leva para a página dele, com a mesma busca.
        if filtro not in jogos_da_loja():
            return redirect(url_for(".listar"))
        return redirect(url_for(".jogo", slug=filtro, q=texto or None))
    _, repositorio = repositorios()
    momento = agora()
    leiloes = repositorio.ativos(momento, texto=texto)
    return render_template("leiloes.html", cartoes=[cartao(leilao, momento) for leilao in leiloes], q=texto)


@bp.get("/jogos/<slug>")
def jogo(slug: str):
    """A página de um jogo: os leilões ativos dele e o espaço dos filtros próprios do jogo."""
    nome = jogos_da_loja().get(slug)
    if nome is None:
        abort(404)
    _, repositorio = repositorios()
    momento, texto = agora(), texto_da_busca()
    cadastrado = next((jogo for jogo in repositorio.jogos() if jogo.nome == nome), None)
    leiloes = repositorio.ativos(momento, cadastrado.id, texto) if cadastrado else []
    return render_template("jogo.html", jogo={"slug": slug, "nome": nome}, q=texto,
                           cartoes=[cartao(leilao, momento) for leilao in leiloes],
                           filtros=FILTROS_POR_JOGO.get(slug))


def _carregar(leilao_id: int):
    _, repositorio = repositorios()
    leilao = repositorio.por_id(leilao_id)
    if leilao is None:
        abort(404)
    # Enquanto a loja não confere a carta e aprova, só o vendedor e o administrador veem o leilão.
    cliente = cliente_atual()
    autorizado = administrador_atual() or (cliente and leilao.carta.vendedor.ehOMesmo(cliente))
    if leilao.status == StatusLeilao.PENDENTE and not autorizado:
        abort(404)
    return leilao, repositorio


@bp.get("/fotos/<arquivo>")
def foto(arquivo: str):
    return send_from_directory(current_app.config["PASTA_DE_FOTOS"], arquivo, max_age=604800)


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
        jogo_slug=slug_de(leilao.carta.jogo.nome),
        erro=erro,
        valor_digitado=valor_digitado,
    ), status


def _json(leilao, momento) -> dict:
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

    registrar_operacao("lance", lance.valor, f"leilão {leilao_id}: {leilao.carta.nome}")
    mensagem = f"Lance de {formatar_reais(lance.valor)} registrado. Você está liderando."
    if quer_json():
        return jsonify(ok=True, mensagem=mensagem, **_json(leilao, momento)), 201
    flash(mensagem, "sucesso")
    return redirect(pagina, code=303)
