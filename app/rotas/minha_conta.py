from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from app.apresentacao import arremate, data_hora, meu_lance, perfil as itens_do_perfil
from app.db import transacao
from app.dominio.dinheiro import ValorMonetarioInvalido, formatar_reais, ler_reais
from app.dominio.financeiro import ZERO, OperacaoRecusada, StatusTransacao
from app.mercado_pago import GatewayIndisponivel
from app.pagamento import FORMAS_DE_PAGAMENTO, abrir_cobranca, conferir_cobranca, pagar_arremate
from app.repositorios.cobrancas import StatusCobranca
from app.rotas.comum import (agora, avisar_pagamento_confirmado, cliente_atual,
                             cobrancas as repositorio_de_cobrancas, login_obrigatorio, registrar_operacao,
                             registrar_pagamento_no_gateway, repositorios, url_publica)

bp = Blueprint("minha_conta", __name__, url_prefix="/minha-conta")


@bp.get("")
@login_obrigatorio
def perfil():
    return render_template("minha_conta/perfil.html", aba="perfil", itens=itens_do_perfil(cliente_atual()))


def _carteira(cliente, erro=None, dados=None, status=200):
    carteira = cliente.carteira
    extrato = [
        {"quando": data_hora(m.dataHora), "descricao": m.descricao, "tipo": m.tipo,
         "valor": formatar_reais(m.valor), "credito": m.valor >= 0}
        for m in carteira.gerarExtrato()
    ]
    saques = [
        {"quando": data_hora(s.dataSolicitacao), "valor": formatar_reais(s.valor), "chave": s.chavePix,
         "status": s.status.capitalize()}
        for s in reversed(carteira.saques)
    ]
    return render_template(
        "minha_conta/carteira.html", aba="carteira", saldo=formatar_reais(carteira.saldo),
        disponivel=formatar_reais(carteira.disponivel), bloqueado=formatar_reais(carteira.bloqueado),
        tem_bloqueio=carteira.bloqueado > 0, pode_sacar=carteira.disponivel > 0, extrato=extrato, saques=saques,
        erro=erro, dados=dados or {}), status


@bp.get("/carteira")
@login_obrigatorio
def carteira():
    return _carteira(cliente_atual())


@bp.post("/carteira/saque")
@login_obrigatorio
def solicitar_saque():
    """RF22: saque do saldo para uma chave Pix (RN16, RN19)."""
    clientes, _ = repositorios()
    dados = {"valor": request.form.get("valor", ""), "chave_pix": request.form.get("chave_pix", "")}
    try:
        valor = ler_reais(dados["valor"])
        with transacao(clientes.conexao, imediata=True):
            cliente = clientes.por_id(cliente_atual().id)
            cliente.carteira.solicitarSaque(valor, dados["chave_pix"], agora())
            clientes.salvar_carteira(cliente)
    except (ValorMonetarioInvalido, OperacaoRecusada) as erro:
        return _carteira(cliente_atual(), str(erro).replace("valor do lance", "valor do saque"), dados, 422)
    registrar_operacao("solicitação de saque", valor, f"Pix {dados['chave_pix'].strip()}")
    flash("Saque solicitado. O valor fica bloqueado até a loja fazer a transferência.", "sucesso")
    return redirect(url_for(".carteira"), code=303)


@bp.get("/lances")
@login_obrigatorio
def lances():
    cliente = cliente_atual()
    momento = agora()
    _, repositorio = repositorios()
    itens = [meu_lance(leilao, cliente, momento) for leilao in repositorio.com_lances_do_cliente(cliente.id)]
    abertos = sorted((item for item in itens if item["aberto"]), key=lambda item: item["fim_iso"])
    encerrados = sorted((item for item in itens if not item["aberto"]), key=lambda item: item["fim_iso"],
                        reverse=True)
    return render_template("minha_conta/lances.html", aba="lances", abertos=abertos, encerrados=encerrados)


@bp.get("/arremates")
@login_obrigatorio
def arremates():
    _, repositorio = repositorios()
    momento = agora()
    itens = [arremate(leilao, momento) for leilao in repositorio.arrematados_por(cliente_atual().id)]
    return render_template("minha_conta/arremates.html", aba="arremates", itens=itens)


def _arremate_a_pagar(leilao_id: int):
    """404 se o arremate não é do cliente logado."""
    _, repositorio = repositorios()
    leilao = repositorio.por_id(leilao_id)
    if leilao is None or leilao.transacao is None or not leilao.transacao.comprador.ehOMesmo(cliente_atual()):
        abort(404)
    return leilao


@bp.route("/arremates/<int:leilao_id>/pagar", methods=["GET", "POST"])
@login_obrigatorio
def pagar(leilao_id: int):
    """RF11: com o saldo da carteira, pelo gateway ou com os dois."""
    clientes, repositorio = repositorios()
    cliente = cliente_atual()
    leilao = _arremate_a_pagar(leilao_id)
    transacao_do_leilao = leilao.transacao
    if transacao_do_leilao.status != StatusTransacao.AGUARDANDO_PAGAMENTO:
        return redirect(url_for(".arremates"))

    gateway = current_app.config["GATEWAY"]
    cobrancas = repositorio_de_cobrancas()
    erro, status = None, 200
    usar_saldo = request.form.get("usar_saldo") == "sim"
    forma = request.form.get("forma", FORMAS_DE_PAGAMENTO[0])
    saldo = cliente.carteira.disponivel
    if request.method == "POST":
        com_saldo = min(saldo, transacao_do_leilao.valor) if usar_saldo else ZERO
        try:
            if gateway.externo and com_saldo < transacao_do_leilao.valor:
                retorno = url_publica("minha_conta.retorno_do_pagamento", leilao_id=leilao_id)
                cobranca = abrir_cobranca(
                    repositorio, cobrancas, gateway, cliente.id, leilao_id, usar_saldo, agora(), retorno=retorno,
                    notificacao=url_publica("pagamentos.notificacao"))
                registrar_operacao("cobrança aberta no gateway", cobranca.valor,
                                   f"leilão {leilao_id}: {leilao.carta.nome} ({gateway.nome})")
                if retorno:
                    return redirect(cobranca.checkoutUrl, code=303)
                # Sem endereço público, o gateway não tem como devolver o comprador: ele paga em outra aba.
                flash(f"Cobrança aberta. Pague no {gateway.nome} e volte aqui para conferir o pagamento.", "info")
                return redirect(url_for(".pagar", leilao_id=leilao_id), code=303)
            pago = pagar_arremate(repositorio, clientes, gateway, cliente.id, leilao_id, usar_saldo, forma,
                                  agora())
        except OperacaoRecusada as recusa:
            erro, status = str(recusa), 422
        except GatewayIndisponivel as falha:
            current_app.logger.warning("Cobrança do leilão %s não aberta: %s", leilao_id, falha)
            erro, status = f"Não foi possível falar com o {gateway.nome} agora. Tente de novo em instantes.", 502
        else:
            registrar_operacao("pagamento de arremate", pago.transacao.valor,
                               f"leilão {leilao_id}: {pago.carta.nome}")
            avisar_pagamento_confirmado(pago)
            flash(f"Pagamento confirmado. Retire {pago.carta.nome} na loja com o código "
                  f"{pago.transacao.codigoRetirada}.", "sucesso")
            return redirect(url_for(".arremates"), code=303)

    pendentes = cobrancas.pendentes_do_leilao(leilao_id) if gateway.externo else []
    return render_template(
        "minha_conta/pagar.html", aba="arremates", item=arremate(leilao, agora()), erro=erro, forma=forma,
        formas=FORMAS_DE_PAGAMENTO, usar_saldo=usar_saldo, tem_saldo=saldo > 0, saldo=formatar_reais(saldo),
        saldo_cobre=saldo >= transacao_do_leilao.valor,
        restante=formatar_reais(max(transacao_do_leilao.valor - saldo, 0)),
        gateway=gateway.nome if gateway.externo else None,
        cobranca=({"url": pendentes[0].checkoutUrl, "valor": formatar_reais(pendentes[0].valor),
                   "quando": data_hora(pendentes[0].dataCriacao)} if pendentes else None)), status


def _conferir_cobrancas(leilao_id: int, referencia: str | None = None, pagamento_id: str | None = None):
    clientes, repositorio = repositorios()
    leilao = _arremate_a_pagar(leilao_id)
    gateway = current_app.config["GATEWAY"]
    if not gateway.externo:
        abort(404)
    cobrancas = repositorio_de_cobrancas()
    try:
        for cobranca in cobrancas.pendentes_do_leilao(leilao_id):
            # O número que veio no endereço só vale para a cobrança daquela referência.
            numero = pagamento_id if cobranca.referencia == referencia else None
            resolvida = conferir_cobranca(repositorio, clientes, cobrancas, gateway, cobranca, agora(), numero)
            if resolvida is not None:
                registrar_pagamento_no_gateway(resolvida, leilao, gateway)
                if resolvida.status == StatusCobranca.PAGA:
                    avisar_pagamento_confirmado(leilao)
    except GatewayIndisponivel as falha:
        current_app.logger.warning("Cobrança do leilão %s não conferida: %s", leilao_id, falha)
        flash(f"Não foi possível consultar o {gateway.nome} agora. Tente conferir de novo em instantes.", "info")
        return redirect(url_for(".pagar", leilao_id=leilao_id), code=303)

    atual = repositorio.por_id(leilao_id)
    if atual.transacao.status == StatusTransacao.PAGO:
        flash(f"Pagamento confirmado. Retire {atual.carta.nome} na loja com o código "
              f"{atual.transacao.codigoRetirada}.", "sucesso")
        return redirect(url_for(".arremates"), code=303)
    if atual.transacao.status != StatusTransacao.AGUARDANDO_PAGAMENTO:
        flash("Este arremate não está mais aguardando pagamento. Se você pagou depois do prazo, o valor foi "
              "creditado na sua carteira.", "info")
        return redirect(url_for(".carteira"), code=303)
    flash(f"O {gateway.nome} ainda não confirmou o pagamento. O Pix costuma ser confirmado em instantes; "
          "confira de novo daqui a pouco.", "info")
    return redirect(url_for(".pagar", leilao_id=leilao_id), code=303)


@bp.get("/arremates/<int:leilao_id>/pagamento")
@login_obrigatorio
def retorno_do_pagamento(leilao_id: int):
    """O que vem no endereço é só uma pista: vale a resposta da API."""
    numero = request.args.get("payment_id") or request.args.get("collection_id") or ""
    return _conferir_cobrancas(leilao_id, request.args.get("external_reference"),
                               numero if numero.isdigit() else None)


@bp.post("/arremates/<int:leilao_id>/pagamento")
@login_obrigatorio
def conferir_pagamento(leilao_id: int):
    return _conferir_cobrancas(leilao_id)
