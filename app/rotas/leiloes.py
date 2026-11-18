from pathlib import Path

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request,
                   send_from_directory, url_for)

from app.apresentacao import cartao, descricao_da_foto, estado, ficha, filtros_para_a_tela, slug as slug_de
from app.db import transacao
from app.dominio.dinheiro import ValorMonetarioInvalido, formatar_reais, ler_reais
from app.dominio.leiloes import LanceRecusado, StatusLeilao
from app.rotas.comum import (administrador_atual, agora, cliente_atual, jogos_da_loja, quer_json,
                             registrar_operacao, repositorios, texto_da_busca)

bp = Blueprint("leiloes", __name__)

PASTA_DAS_CAPAS = "img/jogos"


@bp.get("/")
def inicio():
    _, repositorio = repositorios()
    momento = agora()
    ids = {jogo.nome: jogo.id for jogo in repositorio.jogos()}
    por_jogo = repositorio.ativos_por_jogo(momento)
    jogos = [{"slug": s, "nome": nome, "total": por_jogo.get(ids.get(nome), 0), "capa": _imagem_do_jogo(s),
              "logo": _imagem_do_jogo(s, "logos")} for s, nome in jogos_da_loja().items()]
    return render_template("inicio.html", jogos=jogos,
                           cartoes=[cartao(leilao, momento) for leilao in repositorio.ativos(momento)])


def _imagem_do_jogo(slug_do_jogo: str, subpasta: str = "") -> str | None:
    """None sem o arquivo: sem a logo, o quadrado do jogo mostra o nome escrito."""
    arquivo = "/".join(parte for parte in (PASTA_DAS_CAPAS, subpasta, f"{slug_do_jogo}.webp") if parte)
    return arquivo if (Path(current_app.static_folder) / arquivo).is_file() else None


@bp.get("/leiloes")
def listar():
    filtro, texto = request.args.get("jogo"), texto_da_busca()
    if filtro:
        if filtro not in jogos_da_loja():
            return redirect(url_for(".listar"))
        return redirect(url_for(".jogo", slug=filtro, q=texto or None))
    _, repositorio = repositorios()
    momento = agora()
    leiloes = repositorio.ativos(momento, texto=texto)
    return render_template("leiloes.html", cartoes=[cartao(leilao, momento) for leilao in leiloes], q=texto)


@bp.get("/jogos/<slug>")
def jogo(slug: str):
    nome = jogos_da_loja().get(slug)
    if nome is None:
        abort(404)
    _, repositorio = repositorios()
    momento, texto = agora(), texto_da_busca()
    cadastrado = next((jogo for jogo in repositorio.jogos() if jogo.nome == nome), None)
    catalogo = current_app.config["CATALOGO"]
    definicoes = catalogo.filtros(nome)
    escolhidos = catalogo.filtros_validos(nome, request.args.to_dict(flat=False))
    leiloes = repositorio.ativos(momento, cadastrado.id, texto, escolhidos) if cadastrado else []
    totais = repositorio.atributos_dos_ativos(momento, cadastrado.id) if cadastrado else {}
    return render_template("jogo.html", jogo={"slug": slug, "nome": nome}, q=texto,
                           cartoes=[cartao(leilao, momento) for leilao in leiloes],
                           filtros=filtros_para_a_tela(definicoes, escolhidos, totais),
                           filtrado=bool(escolhidos))


def _carregar(leilao_id: int):
    _, repositorio = repositorios()
    leilao = repositorio.por_id(leilao_id)
    if leilao is None:
        abort(404)
    # Pendente: só o vendedor e o administrador veem o leilão.
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
