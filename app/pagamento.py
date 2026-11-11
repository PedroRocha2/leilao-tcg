from datetime import datetime
from decimal import Decimal

from app.db import transacao
from app.dominio.financeiro import ZERO, OperacaoRecusada
from app.dominio.leiloes import Leilao, StatusCarta
from app.repositorios import RepositorioClientes, RepositorioLeiloes

FORMAS_DE_PAGAMENTO = ("pix", "cartão")


class GatewayLocal:
    """Faz o papel do gateway de pagamento sem cobrar ninguém: confirma na hora.

    Para cobrar de verdade, basta trocar este objeto (configuração GATEWAY) por um que fale com o
    gateway contratado e levante OperacaoRecusada quando a cobrança não for confirmada.
    """

    def cobrar(self, valor: Decimal, forma: str) -> None:
        return None


def pagar_arremate(leiloes: RepositorioLeiloes, clientes: RepositorioClientes, gateway, comprador_id: int,
                   leilao_id: int, usar_saldo: bool, forma: str | None, agora: datetime) -> Leilao:
    """RF11: paga o arremate com o saldo da carteira, pelo gateway (Pix ou cartão) ou com os dois."""
    with transacao(leiloes.conexao, imediata=True):
        leilao = leiloes.por_id(leilao_id)
        arremate = leilao.transacao if leilao else None
        if arremate is None or arremate.comprador.id != comprador_id:
            raise OperacaoRecusada("Este arremate não foi encontrado na sua conta.")
        comprador = arremate.comprador
        com_saldo = min(comprador.carteira.disponivel, arremate.valor) if usar_saldo else ZERO
        no_gateway = arremate.valor - com_saldo
        if no_gateway > 0 and forma not in FORMAS_DE_PAGAMENTO:
            raise OperacaoRecusada("Escolha Pix ou cartão para pagar o valor que o saldo não cobre.")
        # As regras são conferidas antes da cobrança; se o gateway recusar, nada do que mudou é gravado.
        comprador.pagarArremate(arremate, com_saldo, no_gateway, forma, agora)
        if no_gateway > 0:
            gateway.cobrar(no_gateway, forma)
        leilao.carta.atualizarStatus(StatusCarta.PAGA)
        leiloes.salvar_transacao(leilao)
        clientes.salvar_carteira(comprador)
    return leilao
