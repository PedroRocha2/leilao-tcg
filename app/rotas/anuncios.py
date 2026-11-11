import hashlib
import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request, send_file,
                   url_for)

from app.anuncio import TAMANHO_DA_DESCRICAO, AnuncioInvalido, anunciar_carta
from app.apresentacao import FUSO_DA_LOJA, anuncio, descricao_sugerida, preco_de_mercado
from app.catalogo import EXTENSOES, CartaDoCatalogo, Catalogo, CatalogoIndisponivel
from app.catalogo.base import LIMITE_DE_RESULTADOS
from app.dominio.dinheiro import formatar_reais
from app.dominio.leiloes import CONDICOES
from app.rotas.comum import (agora, cliente_atual, jogos_da_loja, loja, login_obrigatorio, registrar_operacao,
                             repositorios)

bp = Blueprint("anuncios", __name__, url_prefix="/vender")

TAMANHO_MINIMO_DA_BUSCA = 2
DURACAO_SUGERIDA = timedelta(days=7)
_CAMPO_DE_DATA = "%Y-%m-%dT%H:%M"


def _catalogo() -> Catalogo:
    return current_app.config["CATALOGO"]


def _fora_do_ar(jogo: str, erro: CatalogoIndisponivel) -> str:
    current_app.logger.warning("Catálogo de %s indisponível: %s", jogo, erro)
    return f"Não foi possível consultar o catálogo de {jogo} agora. Tente de novo em instantes."


@bp.get("")
@login_obrigatorio
def meus_leiloes():
    momento = agora()
    _, repositorio = repositorios()
    itens = [anuncio(leilao, momento) for leilao in repositorio.do_vendedor(cliente_atual().id)]
    return render_template("anuncios/meus_leiloes.html", itens=itens)


@bp.route("/novo", methods=["GET", "POST"])
@login_obrigatorio
def novo():
    jogos = jogos_da_loja()
    escolhido = request.values.get("jogo") or next(iter(jogos))
    if escolhido not in jogos:
        return redirect(url_for(".novo"))
    if not cliente_atual().podeCriarLeilao():
        return render_template("erro.html", titulo="Sua conta está bloqueada",
                               texto="Contas bloqueadas não podem criar leilões. Fale com a loja para "
                                     "regularizar."), 403
    jogo = {"slug": escolhido, "nome": jogos[escolhido]}
    id_da_carta = request.values.get("carta")
    if id_da_carta:
        return _formulario(jogo, id_da_carta)
    return _busca(jogo, jogos)


def _busca(jogo: dict, jogos: dict[str, str]):
    """As cartas do jogo: as sugestões do catálogo ou, com o filtro preenchido, as que o filtro acha."""
    texto = " ".join(request.args.get("q", "").split())
    catalogo = _catalogo()
    cartas, erro, status = [], None, 200
    if texto and len(texto) < TAMANHO_MINIMO_DA_BUSCA:
        erro = f"Digite pelo menos {TAMANHO_MINIMO_DA_BUSCA} caracteres para filtrar as cartas."
    else:
        try:
            cartas = catalogo.buscar(jogo["nome"], texto) if texto else catalogo.sugestoes(jogo["nome"])
        except CatalogoIndisponivel as falha:
            erro, status = _fora_do_ar(jogo["nome"], falha), 502
    chips = [{"nome": nome, "slug": s, "atual": s == jogo["slug"]} for s, nome in jogos.items()]
    return render_template("anuncios/buscar.html", jogo=jogo, chips=chips, q=texto, cartas=cartas, erro=erro,
                           exemplo=catalogo.exemplo_de_codigo(jogo["nome"]),
                           no_limite=len(cartas) >= LIMITE_DE_RESULTADOS), status


def _formulario(jogo: dict, id_da_carta: str):
    try:
        carta = _catalogo().obter(jogo["nome"], id_da_carta)
    except CatalogoIndisponivel as falha:
        return render_template("erro.html", titulo="Catálogo fora do ar",
                               texto=_fora_do_ar(jogo["nome"], falha)), 502
    if carta is None:
        abort(404)

    momento = agora()
    inicio = momento.astimezone(FUSO_DA_LOJA)
    padrao = {"edicao": "", "condicao": "", "descricao": descricao_sugerida(carta.especificacoes),
              "lance_inicial": "", "inicio": inicio.strftime(_CAMPO_DE_DATA),
              "fim": (inicio + DURACAO_SUGERIDA).strftime(_CAMPO_DE_DATA)}
    dados = {campo: request.form.get(campo, valor) for campo, valor in padrao.items()}
    erros: dict[str, str] = {}
    configuracao = loja().configuracao()

    if request.method == "POST":
        _, repositorio = repositorios()
        try:
            leilao = anunciar_carta(
                repositorio, _catalogo(), cliente_atual(), Path(current_app.config["PASTA_DE_FOTOS"]),
                carta=carta, **dados, agora=momento, fuso=FUSO_DA_LOJA, configuracao=configuracao)
        except AnuncioInvalido as invalido:
            erros = invalido.erros
        except CatalogoIndisponivel as falha:
            current_app.logger.warning("Foto de %s não baixada: %s", carta.nome, falha)
            erros = {"foto": "Não foi possível baixar a foto da carta agora. Tente de novo em instantes."}
        else:
            registrar_operacao("criação de leilão", leilao.lanceInicial, f"leilão {leilao.id}: {carta.nome}")
            flash("Leilão criado. Leve a carta à loja: ele começa depois que a loja conferir a carta e "
                  "aprovar.", "sucesso")
            return redirect(url_for(".meus_leiloes"), code=303)

    return render_template(
        "anuncios/carta.html", jogo=jogo, carta=carta, preco=_preco_de_mercado(carta), dados=dados, erros=erros,
        condicoes=CONDICOES, incremento=formatar_reais(configuracao.incrementoMinimo),
        tamanho_da_descricao=TAMANHO_DA_DESCRICAO,
    ), 422 if erros else 200


def _preco_de_mercado(carta: CartaDoCatalogo) -> dict | None:
    """O preço é só uma referência: se o catálogo não responder, o formulário abre sem ele."""
    try:
        return preco_de_mercado(_catalogo().preco(carta))
    except CatalogoIndisponivel as falha:
        current_app.logger.warning("Preço de %s não consultado: %s", carta.nome, falha)
        return None


@bp.get("/miniatura")
@login_obrigatorio
def miniatura():
    """A imagem pequena da carta, servida pela loja: nenhuma página aponta direto para os sites das APIs."""
    jogo = jogos_da_loja().get(request.args.get("jogo", ""))
    try:
        carta = _catalogo().obter(jogo, request.args.get("carta", "")) if jogo else None
        if carta is None:
            abort(404)
        return send_file(_miniatura_em_disco(carta), max_age=86400)
    except CatalogoIndisponivel:
        abort(502)


def _miniatura_em_disco(carta: CartaDoCatalogo) -> Path:
    pasta = Path(current_app.config["PASTA_DO_CATALOGO"])
    chave = hashlib.sha256(f"{carta.jogo}:{carta.id}".encode()).hexdigest()
    guardada = next(pasta.glob(f"{chave}.*"), None)
    if guardada is not None:
        return guardada
    dados, tipo = _catalogo().imagem(carta.miniatura)
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"{chave}{EXTENSOES[tipo]}"
    # Grava com outro nome e troca no fim: dois pedidos da mesma imagem não leem um arquivo pela metade.
    temporario = pasta / f"{uuid4().hex}.tmp"
    temporario.write_bytes(dados)
    os.replace(temporario, arquivo)
    return arquivo
