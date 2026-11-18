"""Área do lojista. Toda rota passa por admin_obrigatorio (RN14, RNF07) e grava no log (RF19)."""
from datetime import datetime, time, timedelta
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from app import administracao
from app.administracao import DadosInvalidos
from app.apresentacao import FUSO_DA_LOJA
from app.db import obter_conexao
from app.dominio.dinheiro import formatar_numero
from app.dominio.financeiro import OperacaoRecusada, StatusSaque, StatusTransacao
from app.dominio.leiloes import CONDICOES
from app.rotas.comum import admin_obrigatorio, agora, loja, registrar_operacao, repositorios

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.context_processor
def pendencias():
    """As pendências do lojista, para os números das abas."""
    conexao = obter_conexao()

    def contar(sql: str) -> int:
        return conexao.execute(sql).fetchone()[0]

    return {"pendencias": {
        "leiloes": contar("SELECT COUNT(*) FROM leiloes WHERE status = 'pendente'"),
        "entregas": contar("SELECT COUNT(*) FROM transacoes WHERE status = 'pago'"),
        "saques": contar("SELECT COUNT(*) FROM saques WHERE status = 'solicitado'"),
    }}


def _recusada(erro: OperacaoRecusada, destino: str):
    flash(str(erro), "info")
    return redirect(destino, code=303)


@bp.get("")
@admin_obrigatorio
def inicio():
    return redirect(url_for(".leiloes"))


@bp.get("/leiloes")
@admin_obrigatorio
def leiloes():
    _, repositorio = repositorios()
    return render_template("admin/leiloes.html", aba="leiloes", pendentes=repositorio.pendentes(),
                           a_retirar=repositorio.com_transacao(StatusTransacao.PAGO))


@bp.post("/leiloes/<int:numero>/aprovar")
@admin_obrigatorio
def aprovar(numero: int):
    _, repositorio = repositorios()
    try:
        leilao = administracao.aprovar_leilao(repositorio, numero, agora())
    except OperacaoRecusada as erro:
        return _recusada(erro, url_for(".leiloes"))
    registrar_operacao("aprovação de leilão", detalhe=f"leilão {numero}: {leilao.carta.nome}, depósito registrado")
    quando = "já está recebendo lances" if leilao.estaAberto(agora()) else "começa na data de início"
    flash(f"Leilão {numero} ({leilao.carta.nome}) aprovado: {quando}.", "sucesso")
    return redirect(url_for(".leiloes"), code=303)


@bp.post("/leiloes/<int:numero>/recusar")
@admin_obrigatorio
def recusar(numero: int):
    _, repositorio = repositorios()
    try:
        leilao = administracao.recusar_leilao(repositorio, numero, request.form.get("motivo", ""))
    except OperacaoRecusada as erro:
        return _recusada(erro, url_for(".leiloes"))
    registrar_operacao("recusa de leilão", detalhe=f"leilão {numero}: {leilao.motivoRecusa}")
    flash(f"Leilão {numero} ({leilao.carta.nome}) recusado. O vendedor vê o motivo em Vender.", "sucesso")
    return redirect(url_for(".leiloes"), code=303)


@bp.get("/entregas")
@admin_obrigatorio
def entregas():
    _, repositorio = repositorios()
    return render_template("admin/entregas.html", aba="entregas",
                           a_retirar=repositorio.com_transacao(StatusTransacao.PAGO))


@bp.route("/entregas/<int:numero>", methods=["GET", "POST"])
@admin_obrigatorio
def entrega(numero: int):
    """RF12: confere o código de retirada e confirma a entrega."""
    clientes, repositorio = repositorios()
    leilao = repositorio.por_id(numero)
    if leilao is None or leilao.transacao is None:
        abort(404)
    if request.method == "POST":
        try:
            leilao = administracao.registrar_entrega(repositorio, clientes, numero, request.form.get("codigo", ""),
                                                     agora())
        except OperacaoRecusada as erro:
            return _recusada(erro, url_for(".entrega", numero=numero))
        arremate = leilao.transacao
        registrar_operacao("entrega e repasse", arremate.valorLiquido,
                           f"leilão {leilao.id}: {leilao.carta.nome}, repasse a {arremate.vendedor.nome}")
        flash(f"Entrega de {leilao.carta.nome} registrada. O repasse ao vendedor foi creditado na carteira dele.",
              "sucesso")
        return redirect(url_for(".leiloes"), code=303)
    return render_template("admin/entrega.html", aba="entregas", leilao=leilao)


@bp.get("/saques")
@admin_obrigatorio
def saques():
    clientes, _ = repositorios()
    todos = clientes.saques()
    return render_template(
        "admin/saques.html", aba="saques",
        solicitados=[par for par in reversed(todos) if par[0].status == StatusSaque.SOLICITADO],
        respondidos=[par for par in todos if par[0].status != StatusSaque.SOLICITADO])


@bp.post("/saques/<int:saque_id>/<any(pagar, recusar):acao>")
@admin_obrigatorio
def responder_saque(saque_id: int, acao: str):
    clientes, _ = repositorios()
    try:
        saque, cliente = administracao.responder_saque(clientes, saque_id, acao == "pagar", agora())
    except OperacaoRecusada as erro:
        return _recusada(erro, url_for(".saques"))
    if acao == "pagar":
        registrar_operacao("saque pago", saque.valor, f"{cliente.nome}, Pix {saque.chavePix}")
        flash(f"Transferência registrada: saque de {cliente.nome} pago.", "sucesso")
    else:
        registrar_operacao("saque recusado", saque.valor, cliente.nome)
        flash(f"Saque de {cliente.nome} recusado. O valor voltou ao saldo disponível dele.", "sucesso")
    return redirect(url_for(".saques"), code=303)


@bp.get("/usuarios")
@admin_obrigatorio
def usuarios():
    clientes, _ = repositorios()
    return render_template("admin/usuarios.html", aba="usuarios", clientes=clientes.todos())


def _cliente(cliente_id: int):
    clientes, _ = repositorios()
    cliente = clientes.por_id(cliente_id)
    if cliente is None:
        abort(404)
    return clientes, cliente


@bp.route("/usuarios/<int:cliente_id>", methods=["GET", "POST"])
@admin_obrigatorio
def usuario(cliente_id: int):
    clientes, cliente = _cliente(cliente_id)
    dados = {campo: request.form.get(campo, getattr(cliente, campo)) for campo in ("nome", "email", "telefone")}
    erros: dict[str, str] = {}
    if request.method == "POST":
        try:
            administracao.atualizar_cliente(clientes, cliente, **dados)
        except DadosInvalidos as invalido:
            erros = invalido.erros
        else:
            registrar_operacao("edição de usuário", detalhe=f"cliente {cliente.id}: {cliente.nome}")
            flash(f"Dados de {cliente.nome} atualizados.", "sucesso")
            return redirect(url_for(".usuario", cliente_id=cliente.id), code=303)
    return render_template("admin/usuario.html", aba="usuarios", c=cliente, dados=dados, erros=erros), (
        422 if erros else 200)


@bp.post("/usuarios/<int:cliente_id>/<any(bloquear, desbloquear):acao>")
@admin_obrigatorio
def bloqueio(cliente_id: int, acao: str):
    clientes, cliente = _cliente(cliente_id)
    administracao.definir_bloqueio(clientes, cliente, acao == "bloquear")
    registrar_operacao("bloqueio de conta" if cliente.bloqueado else "desbloqueio de conta",
                       detalhe=f"cliente {cliente.id}: {cliente.nome}")
    flash(f"Conta de {cliente.nome} {'bloqueada' if cliente.bloqueado else 'desbloqueada'}.", "sucesso")
    return redirect(url_for(".usuario", cliente_id=cliente.id), code=303)


@bp.get("/cartas")
@admin_obrigatorio
def cartas():
    _, repositorio = repositorios()
    return render_template("admin/cartas.html", aba="cartas", leiloes=repositorio.todos())


def _leilao(numero: int):
    _, repositorio = repositorios()
    leilao = repositorio.por_id(numero)
    if leilao is None:
        abort(404)
    return repositorio, leilao


@bp.route("/cartas/<int:numero>", methods=["GET", "POST"])
@admin_obrigatorio
def carta(numero: int):
    repositorio, leilao = _leilao(numero)
    atual = leilao.carta
    padrao = {"nome": atual.nome, "jogo": str(atual.jogo.id), "edicao": atual.edicao, "condicao": atual.condicao}
    dados = {campo: request.form.get(campo, valor) for campo, valor in padrao.items()}
    erros: dict[str, str] = {}
    if request.method == "POST":
        try:
            administracao.atualizar_carta(repositorio, leilao, dados["nome"], dados["jogo"], dados["edicao"],
                                          dados["condicao"])
        except DadosInvalidos as invalido:
            erros = invalido.erros
        else:
            registrar_operacao("edição de carta", detalhe=f"leilão {numero}: {leilao.carta.nome}")
            flash(f"Dados de {leilao.carta.nome} atualizados.", "sucesso")
            return redirect(url_for(".carta", numero=numero), code=303)
    condicoes = CONDICOES if atual.condicao in CONDICOES else (atual.condicao, *CONDICOES)
    return render_template(
        "admin/carta.html", aba="cartas", leilao=leilao, dados=dados, erros=erros, jogos=repositorio.jogos(),
        condicoes=condicoes, pode_remover=administracao.pode_remover(leilao)), 422 if erros else 200


@bp.post("/cartas/<int:numero>/remover")
@admin_obrigatorio
def remover_carta(numero: int):
    repositorio, leilao = _leilao(numero)
    try:
        administracao.remover_carta(repositorio, leilao, Path(current_app.config["PASTA_DE_FOTOS"]))
    except OperacaoRecusada as erro:
        return _recusada(erro, url_for(".carta", numero=numero))
    registrar_operacao("remoção de carta", detalhe=f"leilão {numero}: {leilao.carta.nome}")
    flash(f"Cadastro de {leilao.carta.nome} removido.", "sucesso")
    return redirect(url_for(".cartas"), code=303)


@bp.get("/historico")
@admin_obrigatorio
def historico():
    _, repositorio = repositorios()
    linhas = [(leilao, administracao.desfecho(leilao)) for leilao in repositorio.finalizados()]
    return render_template("admin/historico.html", aba="historico", linhas=linhas)


def _dia(texto: str | None, padrao):
    try:
        return datetime.strptime(texto or "", "%Y-%m-%d").date()
    except ValueError:
        return padrao


@bp.get("/financeiro")
@admin_obrigatorio
def financeiro():
    clientes, repositorio = repositorios()
    hoje = agora().astimezone(FUSO_DA_LOJA).date()
    de = _dia(request.args.get("de"), hoje.replace(day=1))
    ate = max(_dia(request.args.get("ate"), hoje), de)
    extrato = administracao.extrato_financeiro(
        repositorio, clientes,
        datetime.combine(de, time.min, FUSO_DA_LOJA),
        datetime.combine(ate + timedelta(days=1), time.min, FUSO_DA_LOJA))
    return render_template("admin/financeiro.html", aba="financeiro", de=de.isoformat(), ate=ate.isoformat(),
                           **extrato)


@bp.route("/configuracoes", methods=["GET", "POST"])
@admin_obrigatorio
def configuracoes():
    atual = loja().configuracao()
    padrao = {"taxa": formatar_numero(atual.taxaPercentual), "incremento": formatar_numero(atual.incrementoMinimo),
              "prazo_pagamento": str(atual.prazoPagamentoHoras), "prazo_reoferta": str(atual.prazoReofertaHoras)}
    dados = {campo: request.form.get(campo, valor) for campo, valor in padrao.items()}
    erros: dict[str, str] = {}
    if request.method == "POST":
        try:
            nova = administracao.configurar_loja(loja(), **dados)
        except DadosInvalidos as invalido:
            erros = invalido.erros
        else:
            registrar_operacao(
                "configuração da loja",
                detalhe=f"taxa {formatar_numero(nova.taxaPercentual)}%, incremento "
                        f"{formatar_numero(nova.incrementoMinimo)}, pagamento em {nova.prazoPagamentoHoras} h, "
                        f"reoferta em {nova.prazoReofertaHoras} h")
            flash("Configurações salvas. A taxa e o incremento valem para os leilões criados a partir de agora.",
                  "sucesso")
            return redirect(url_for(".configuracoes"), code=303)
    return render_template("admin/configuracoes.html", aba="configuracoes", dados=dados, erros=erros), (
        422 if erros else 200)


@bp.get("/auditoria")
@admin_obrigatorio
def auditoria():
    return render_template("admin/auditoria.html", aba="auditoria", operacoes=loja().operacoes())
