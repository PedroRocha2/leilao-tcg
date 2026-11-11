from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for

from app.apresentacao import arremate, data_hora, meu_lance, perfil as itens_do_perfil
from app.db import transacao
from app.dominio.dinheiro import ValorMonetarioInvalido, formatar_reais, ler_reais
from app.dominio.financeiro import OperacaoRecusada, StatusTransacao
from app.pagamento import FORMAS_DE_PAGAMENTO, pagar_arremate
from app.rotas.comum import agora, cliente_atual, login_obrigatorio, registrar_operacao, repositorios

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
    """RF22: o cliente pede o saque do saldo, com a chave Pix de destino (RN16, RN19)."""
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


@bp.route("/arremates/<int:leilao_id>/pagar", methods=["GET", "POST"])
@login_obrigatorio
def pagar(leilao_id: int):
    """RF11: paga o arremate com o saldo da carteira, por Pix ou cartão, ou com os dois."""
    clientes, repositorio = repositorios()
    cliente = cliente_atual()
    leilao = repositorio.por_id(leilao_id)
    if leilao is None or leilao.transacao is None or not leilao.transacao.comprador.ehOMesmo(cliente):
        abort(404)
    transacao_do_leilao = leilao.transacao
    if transacao_do_leilao.status != StatusTransacao.AGUARDANDO_PAGAMENTO:
        return redirect(url_for(".arremates"))

    erro = None
    usar_saldo = request.form.get("usar_saldo") == "sim"
    forma = request.form.get("forma", FORMAS_DE_PAGAMENTO[0])
    if request.method == "POST":
        try:
            pago = pagar_arremate(repositorio, clientes, current_app.config["GATEWAY"], cliente.id, leilao_id,
                                  usar_saldo, forma, agora())
        except OperacaoRecusada as recusa:
            erro = str(recusa)
        else:
            registrar_operacao("pagamento de arremate", pago.transacao.valor,
                               f"leilão {leilao_id}: {pago.carta.nome}")
            flash(f"Pagamento confirmado. Retire {pago.carta.nome} na loja com o código "
                  f"{pago.transacao.codigoRetirada}.", "sucesso")
            return redirect(url_for(".arremates"), code=303)

    saldo = cliente.carteira.disponivel
    return render_template(
        "minha_conta/pagar.html", aba="arremates", item=arremate(leilao, agora()), erro=erro, forma=forma,
        formas=FORMAS_DE_PAGAMENTO, usar_saldo=usar_saldo, tem_saldo=saldo > 0, saldo=formatar_reais(saldo),
        saldo_cobre=saldo >= transacao_do_leilao.valor,
        restante=formatar_reais(max(transacao_do_leilao.valor - saldo, 0))), 422 if erro else 200
