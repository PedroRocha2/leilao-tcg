from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from app.dominio.dinheiro import formatar_reais

if TYPE_CHECKING:
    from app.dominio.contas import Cliente

ZERO = Decimal("0.00")
# Sem I, L, O, 0 e 1, que se confundem ao ditar o código.
_ALFABETO_DO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def novo_codigo_de_retirada() -> str:
    return "".join(secrets.choice(_ALFABETO_DO_CODIGO) for _ in range(8))


class OperacaoRecusada(Exception):
    """A mensagem vai para a tela."""


@dataclass(eq=False)
class MovimentacaoCarteira:
    tipo: str
    valor: Decimal
    dataHora: datetime
    descricao: str
    id: int | None = None


class StatusSaque(StrEnum):
    SOLICITADO = "solicitado"
    PAGO = "pago"
    RECUSADO = "recusado"


@dataclass(eq=False)
class Saque:
    valor: Decimal
    chavePix: str
    dataSolicitacao: datetime
    status: str = StatusSaque.SOLICITADO
    dataResposta: datetime | None = None
    id: int | None = None


@dataclass(eq=False)
class Carteira:
    saldo: Decimal = ZERO
    movimentacoes: list[MovimentacaoCarteira] = field(default_factory=list)
    bloqueado: Decimal = ZERO
    saques: list[Saque] = field(default_factory=list)
    id: int | None = None

    @property
    def disponivel(self) -> Decimal:
        """RN19: sem o valor reservado por saques solicitados."""
        return self.saldo - self.bloqueado

    def gerarExtrato(self) -> list[MovimentacaoCarteira]:
        return sorted(self.movimentacoes, key=lambda m: m.dataHora, reverse=True)

    def possuiSaldo(self, valor: Decimal) -> bool:
        return valor <= self.disponivel

    def creditar(self, valor: Decimal, descricao: str, agora: datetime) -> None:
        if valor <= 0:
            raise ValueError("O crédito precisa ser maior que zero.")
        self.saldo += valor
        self.movimentacoes.append(MovimentacaoCarteira("crédito", valor, agora, descricao))

    def debitar(self, valor: Decimal, descricao: str, agora: datetime) -> None:
        if valor <= 0:
            raise ValueError("O débito precisa ser maior que zero.")
        if not self.possuiSaldo(valor):
            raise OperacaoRecusada("O saldo disponível na carteira não cobre este valor.")
        self.saldo -= valor
        self.movimentacoes.append(MovimentacaoCarteira("débito", -valor, agora, descricao))

    def solicitarSaque(self, valor: Decimal, chavePix: str, agora: datetime) -> Saque:
        """RN16: só até o saldo disponível. RN19: o valor fica bloqueado até a resposta da loja."""
        if valor <= 0:
            raise OperacaoRecusada("Informe um valor maior que zero.")
        if not self.possuiSaldo(valor):
            raise OperacaoRecusada(
                f"O saque não pode passar do saldo disponível, que é {formatar_reais(self.disponivel)}.")
        if not chavePix.strip():
            raise OperacaoRecusada("Informe a chave Pix de destino.")
        saque = Saque(valor=valor, chavePix=chavePix.strip(), dataSolicitacao=agora)
        self.bloqueado += valor
        self.saques.append(saque)
        return saque

    def pagarSaque(self, saque: Saque, agora: datetime) -> None:
        self._responder(saque, StatusSaque.PAGO, agora)
        self.saldo -= saque.valor
        self.movimentacoes.append(
            MovimentacaoCarteira("débito", -saque.valor, agora, f"Saque por Pix para {saque.chavePix}"))

    def recusarSaque(self, saque: Saque, agora: datetime) -> None:
        """RN19: o valor bloqueado volta a ficar disponível."""
        self._responder(saque, StatusSaque.RECUSADO, agora)

    def _responder(self, saque: Saque, status: StatusSaque, agora: datetime) -> None:
        if saque.status != StatusSaque.SOLICITADO:
            raise OperacaoRecusada("Este saque já foi respondido.")
        saque.status = status
        saque.dataResposta = agora
        self.bloqueado -= saque.valor


class StatusTransacao(StrEnum):
    AGUARDANDO_PAGAMENTO = "aguardando pagamento"
    PAGO = "pago"
    ENTREGUE = "entregue"
    NAO_PAGA = "não paga"


@dataclass(eq=False)
class Transacao:
    """O arremate."""
    valor: Decimal
    dataHora: datetime
    comprador: Cliente
    vendedor: Cliente
    prazoPagamento: datetime
    taxa: Decimal = ZERO
    status: str = StatusTransacao.AGUARDANDO_PAGAMENTO
    codigoRetirada: str = field(default_factory=novo_codigo_de_retirada)
    dataPagamento: datetime | None = None
    dataEntrega: datetime | None = None
    pagoComSaldo: Decimal = ZERO
    pagoNoGateway: Decimal = ZERO
    formaDePagamento: str | None = None
    id: int | None = None

    @property
    def valorLiquido(self) -> Decimal:
        """RN09: a taxa da loja sai do valor do arremate; o resto é do vendedor."""
        return self.valor - self.taxa

    def confirmarPagamento(self, comSaldo: Decimal, noGateway: Decimal, forma: str | None,
                           agora: datetime) -> None:
        if self.status != StatusTransacao.AGUARDANDO_PAGAMENTO:
            raise OperacaoRecusada("Este arremate não está aguardando pagamento.")
        if agora >= self.prazoPagamento:
            raise OperacaoRecusada("O prazo de pagamento deste arremate terminou.")
        if comSaldo < 0 or noGateway < 0 or comSaldo + noGateway != self.valor:
            raise ValueError("O pagamento precisa cobrir exatamente o valor do arremate.")
        self.status = StatusTransacao.PAGO
        self.dataPagamento = agora
        self.pagoComSaldo, self.pagoNoGateway = comSaldo, noGateway
        self.formaDePagamento = forma if noGateway > 0 else None

    def registrarEntrega(self, codigo: str, agora: datetime) -> None:
        """RN07."""
        if (codigo or "").strip().upper() != self.codigoRetirada:
            raise OperacaoRecusada("O código de retirada não confere com este arremate.")
        if self.status == StatusTransacao.ENTREGUE:
            raise OperacaoRecusada("Esta carta já foi entregue.")
        if self.status != StatusTransacao.PAGO:
            raise OperacaoRecusada("A carta só pode ser entregue depois do pagamento do arremate.")
        self.status = StatusTransacao.ENTREGUE
        self.dataEntrega = agora

    def expirar(self, agora: datetime) -> None:
        """RN06."""
        if self.status != StatusTransacao.AGUARDANDO_PAGAMENTO or agora < self.prazoPagamento:
            raise ValueError("Só expira o arremate que aguarda pagamento e passou do prazo.")
        self.status = StatusTransacao.NAO_PAGA
