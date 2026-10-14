"""Minha Conta: Perfil, Carteira (só leitura) e Meus lances."""

from flask import Blueprint, render_template

from app.apresentacao import data_hora, meu_lance, perfil as itens_do_perfil
from app.dominio.dinheiro import formatar_reais
from app.rotas.comum import agora, cliente_atual, login_obrigatorio, repositorios

bp = Blueprint("minha_conta", __name__, url_prefix="/minha-conta")


@bp.get("")
@login_obrigatorio
def perfil():
    return render_template("minha_conta/perfil.html", aba="perfil", itens=itens_do_perfil(cliente_atual()))


@bp.get("/carteira")
@login_obrigatorio
def carteira():
    carteira = cliente_atual().carteira
    extrato = [
        {"quando": data_hora(m.dataHora), "descricao": m.descricao, "tipo": m.tipo,
         "valor": formatar_reais(m.valor), "credito": m.valor >= 0}
        for m in carteira.gerarExtrato()
    ]
    return render_template("minha_conta/carteira.html", aba="carteira",
                           saldo=formatar_reais(carteira.saldo), extrato=extrato)


@bp.get("/lances")
@login_obrigatorio
def lances():
    cliente = cliente_atual()
    momento = agora()
    _, repositorio = repositorios()
    itens = [meu_lance(leilao, cliente, momento) for leilao in repositorio.com_lances_do_cliente(cliente.id)]
    # Os que ainda recebem lances, com os que terminam antes no topo; depois os encerrados, do mais recente.
    abertos = sorted((item for item in itens if item["aberto"]), key=lambda item: item["fim_iso"])
    encerrados = sorted((item for item in itens if not item["aberto"]), key=lambda item: item["fim_iso"],
                        reverse=True)
    return render_template("minha_conta/lances.html", aba="lances", abertos=abertos, encerrados=encerrados)
