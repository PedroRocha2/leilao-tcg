import secrets
from datetime import datetime
from decimal import Decimal

from app.db import transacao
from app.dominio.financeiro import ZERO, OperacaoRecusada, StatusTransacao
from app.dominio.leiloes import Leilao, StatusCarta
from app.mercado_pago import MOEDA, PagamentoNoGateway
from app.repositorios import RepositorioClientes, RepositorioLeiloes
from app.repositorios.cobrancas import Cobranca, RepositorioCobrancas, StatusCobranca

FORMAS_DE_PAGAMENTO = ("pix", "cartão")


class GatewayLocal:
    """Sem credencial do Mercado Pago: confirma na hora, sem cobrar."""
    externo = False
    nome = "gateway local"

    def cobrar(self, valor: Decimal, forma: str) -> None:
        return None


def _arremate_do_comprador(leiloes: RepositorioLeiloes, comprador_id: int, leilao_id: int) -> Leilao:
    leilao = leiloes.por_id(leilao_id)
    arremate = leilao.transacao if leilao else None
    if arremate is None or arremate.comprador.id != comprador_id:
        raise OperacaoRecusada("Este arremate não foi encontrado na sua conta.")
    return leilao


def pagar_arremate(leiloes: RepositorioLeiloes, clientes: RepositorioClientes, gateway, comprador_id: int,
                   leilao_id: int, usar_saldo: bool, forma: str | None, agora: datetime) -> Leilao:
    """RF11: saldo, gateway local ou os dois. Com gateway externo, só quando o saldo cobre tudo."""
    with transacao(leiloes.conexao, imediata=True):
        leilao = _arremate_do_comprador(leiloes, comprador_id, leilao_id)
        arremate = leilao.transacao
        comprador = arremate.comprador
        com_saldo = min(comprador.carteira.disponivel, arremate.valor) if usar_saldo else ZERO
        no_gateway = arremate.valor - com_saldo
        if no_gateway > 0 and gateway.externo:
            raise OperacaoRecusada(f"O saldo não cobre o arremate. Pague o restante pelo {gateway.nome}.")
        if no_gateway > 0 and forma not in FORMAS_DE_PAGAMENTO:
            raise OperacaoRecusada("Escolha Pix ou cartão para pagar o valor que o saldo não cobre.")
        # Regras antes da cobrança; se o gateway recusar, a transação desfaz tudo.
        comprador.pagarArremate(arremate, com_saldo, no_gateway, forma, agora)
        if no_gateway > 0:
            gateway.cobrar(no_gateway, forma)
        leilao.carta.atualizarStatus(StatusCarta.PAGA)
        leiloes.salvar_transacao(leilao)
        clientes.salvar_carteira(comprador)
    return leilao


def abrir_cobranca(leiloes: RepositorioLeiloes, cobrancas: RepositorioCobrancas, gateway, comprador_id: int,
                   leilao_id: int, usar_saldo: bool, agora: datetime, retorno: str | None = None,
                   notificacao: str | None = None) -> Cobranca:
    """RF11: nada é pago aqui; o saldo só é debitado na confirmação (RN18)."""
    leilao = _arremate_do_comprador(leiloes, comprador_id, leilao_id)
    arremate = leilao.transacao
    if arremate.status != StatusTransacao.AGUARDANDO_PAGAMENTO:
        raise OperacaoRecusada("Este arremate não está aguardando pagamento.")
    if agora >= arremate.prazoPagamento:
        raise OperacaoRecusada("O prazo de pagamento deste arremate terminou.")
    com_saldo = min(arremate.comprador.carteira.disponivel, arremate.valor) if usar_saldo else ZERO
    no_gateway = arremate.valor - com_saldo
    if no_gateway <= 0:
        raise OperacaoRecusada("O saldo da carteira cobre este arremate inteiro.")

    # Reaproveita a cobrança pendente em vez de abrir outra.
    for pendente in cobrancas.pendentes_do_leilao(leilao.id):
        if (pendente.valor, pendente.comSaldo) == (no_gateway, com_saldo):
            return pendente
    referencia = f"leilao-{leilao.id}-{secrets.token_hex(8)}"
    checkout = gateway.criar_checkout(
        referencia=referencia, titulo=f"{leilao.carta.nome} ({leilao.carta.edicao}): arremate do leilão {leilao.id}",
        valor=no_gateway, expira=arremate.prazoPagamento, retorno=retorno, notificacao=notificacao)
    return cobrancas.adicionar(Cobranca(
        leilaoId=leilao.id, referencia=referencia, valor=no_gateway, comSaldo=com_saldo,
        checkoutId=checkout.id, checkoutUrl=checkout.url, dataCriacao=agora))


def conferir_cobranca(leiloes: RepositorioLeiloes, clientes: RepositorioClientes, cobrancas: RepositorioCobrancas,
                      gateway, cobranca: Cobranca, agora: datetime,
                      pagamento_id: str | None = None) -> Cobranca | None:
    """Devolve a cobrança só quando esta conferência a resolveu."""
    if cobranca.status != StatusCobranca.PENDENTE:
        return None
    pagamentos = gateway.pagamentos(cobranca.referencia)
    if pagamento_id and not any(pagamento.aprovado for pagamento in pagamentos):
        # A busca do gateway demora a enxergar pagamentos recentes.
        pagamentos = [gateway.pagamento(pagamento_id)]
    return _liquidar(leiloes, clientes, cobrancas, gateway, cobranca.referencia, pagamentos, agora)


def confirmar_pagamento(leiloes: RepositorioLeiloes, clientes: RepositorioClientes,
                        cobrancas: RepositorioCobrancas, gateway, pagamento_id: str,
                        agora: datetime) -> Cobranca | None:
    """Webhook. Devolve a cobrança só quando este aviso a resolveu: o gateway repete os avisos."""
    pagamento = gateway.pagamento(pagamento_id)
    if pagamento is None:
        return None
    return _liquidar(leiloes, clientes, cobrancas, gateway, pagamento.referencia, [pagamento], agora)


def _liquidar(leiloes: RepositorioLeiloes, clientes: RepositorioClientes, cobrancas: RepositorioCobrancas,
              gateway, referencia: str, pagamentos: list[PagamentoNoGateway | None],
              agora: datetime) -> Cobranca | None:
    """Devolve a cobrança só quando esta chamada a resolveu, para o log registrar uma vez."""
    with transacao(leiloes.conexao, imediata=True):
        # Relê com o banco travado: a volta do comprador e o webhook chegam quase juntos.
        cobranca = cobrancas.por_referencia(referencia) if referencia else None
        if cobranca is None or cobranca.status != StatusCobranca.PENDENTE:
            return None
        aprovado = next((p for p in pagamentos if p is not None and p.aprovado and p.referencia == referencia
                         and p.valor == cobranca.valor and p.moeda == MOEDA), None)
        if aprovado is None:
            return None
        leilao = leiloes.por_id(cobranca.leilaoId)
        arremate = leilao.transacao
        comprador = arremate.comprador
        try:
            comprador.pagarArremate(arremate, cobranca.comSaldo, cobranca.valor, aprovado.forma, agora)
        except OperacaoRecusada as motivo:
            # O dinheiro entrou mas não quita mais o arremate: vai para a carteira.
            comprador.carteira.creditar(
                cobranca.valor, f"Pagamento pelo {gateway.nome} não aplicado ao arremate de {leilao.carta.nome}: "
                                f"{str(motivo).rstrip('.')}", agora)
            cobranca.status = StatusCobranca.CREDITADA
        else:
            leilao.carta.atualizarStatus(StatusCarta.PAGA)
            leiloes.salvar_transacao(leilao)
            cobranca.status = StatusCobranca.PAGA
        clientes.salvar_carteira(comprador)
        cobranca.pagamentoId, cobranca.dataResposta = aprovado.id, agora
        cobrancas.salvar(cobranca)
    return cobranca
