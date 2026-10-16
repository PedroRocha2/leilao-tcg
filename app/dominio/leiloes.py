from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from app.dominio.dinheiro import formatar_reais

if TYPE_CHECKING:
    from app.dominio.contas import Cliente

JANELA_DE_PRORROGACAO = timedelta(minutes=3)
PRORROGACAO = timedelta(minutes=3)


class StatusLeilao(StrEnum):
    PENDENTE = "pendente"
    APROVADO = "aprovado"
    ATIVO = "ativo"
    ENCERRADO = "encerrado"
    CANCELADO = "cancelado"


class MotivoRecusa(StrEnum):
    CLIENTE_BLOQUEADO = "cliente_bloqueado"
    PROPRIO_LEILAO = "proprio_leilao"
    LEILAO_INATIVO = "leilao_inativo"
    LEILAO_NAO_INICIADO = "leilao_nao_iniciado"
    PRAZO_ENCERRADO = "prazo_encerrado"
    VALOR_INVALIDO = "valor_invalido"
    ABAIXO_DO_MINIMO = "abaixo_do_minimo"


class LanceRecusado(Exception):
    def __init__(self, motivo: MotivoRecusa, mensagem: str):
        super().__init__(mensagem)
        self.motivo = motivo
        self.mensagem = mensagem


@dataclass(eq=False)
class Jogo:
    nome: str
    id: int | None = None


@dataclass(eq=False)
class Carta:
    nome: str
    jogo: Jogo
    edicao: str
    condicao: str
    descricao: str
    vendedor: Cliente
    status: str
    fotos: list[str] = field(default_factory=list)
    id: int | None = None

    def adicionarFoto(self, url: str) -> None:
        self.fotos.append(url)


@dataclass(frozen=True, eq=False)
class Lance:
    valor: Decimal
    dataHora: datetime
    cliente: Cliente
    id: int | None = None


@dataclass(eq=False)
class Leilao:
    carta: Carta
    lanceInicial: Decimal
    incrementoMinimo: Decimal
    dataInicio: datetime
    dataFimPrevista: datetime
    status: str
    dataFimReal: datetime | None = None
    lances: list[Lance] = field(default_factory=list)
    id: int | None = None

    def __post_init__(self):
        if self.dataFimPrevista <= self.dataInicio:
            raise ValueError("RN05: o fim previsto do leilão precisa ser depois do início.")
        if self.lanceInicial <= 0 or self.incrementoMinimo <= 0:
            raise ValueError("O lance inicial e o incremento mínimo precisam ser maiores que zero.")

    def getMaiorLance(self) -> Lance | None:
        maior = None
        for lance in self.lances:
            if (maior is None or lance.valor > maior.valor
                    or (lance.valor == maior.valor and lance.dataHora < maior.dataHora)):
                maior = lance
        return maior

    def calcularLanceMinimo(self) -> Decimal:
        maior = self.getMaiorLance()
        if maior is None:
            return self.lanceInicial
        return maior.valor + self.incrementoMinimo

    def validarLance(self, valor: Decimal, agora: datetime | None = None) -> bool:
        return self.motivoDeRecusa(valor, agora) is None

    def estaAberto(self, agora: datetime) -> bool:
        return self.status == StatusLeilao.ATIVO and self.dataInicio <= agora < self.dataFimPrevista

    def motivoDeRecusa(self, valor: Decimal, agora: datetime | None = None) -> MotivoRecusa | None:
        agora = agora or datetime.now(UTC)
        if self.status != StatusLeilao.ATIVO:
            return MotivoRecusa.LEILAO_INATIVO
        if agora < self.dataInicio:
            return MotivoRecusa.LEILAO_NAO_INICIADO
        if agora >= self.dataFimPrevista:
            return MotivoRecusa.PRAZO_ENCERRADO
        if valor <= 0:
            return MotivoRecusa.VALOR_INVALIDO
        if valor < self.calcularLanceMinimo():
            return MotivoRecusa.ABAIXO_DO_MINIMO
        return None

    def explicarRecusa(self, motivo: MotivoRecusa) -> str:
        if motivo is MotivoRecusa.ABAIXO_DO_MINIMO:
            maior = self.getMaiorLance()
            if maior is None:
                return (f"O primeiro lance precisa ser de pelo menos {formatar_reais(self.lanceInicial)}, "
                        f"o lance inicial deste leilão.")
            return (f"O lance mínimo agora é {formatar_reais(self.calcularLanceMinimo())}: maior lance "
                    f"({formatar_reais(maior.valor)}) + incremento mínimo "
                    f"({formatar_reais(self.incrementoMinimo)}).")
        return {
            MotivoRecusa.LEILAO_INATIVO: ("Este leilão não está ativo e não recebe lances. "
                                          "Escolha outro na lista de leilões."),
            MotivoRecusa.LEILAO_NAO_INICIADO: ("Este leilão ainda não começou. "
                                               "Volte na data de início para dar seu lance."),
            MotivoRecusa.PRAZO_ENCERRADO: ("O prazo deste leilão terminou. "
                                           "Escolha outro na lista de leilões ativos."),
            MotivoRecusa.VALOR_INVALIDO: "Informe um valor maior que zero, como 2.355,00.",
        }[motivo]

    def receberLance(self, lance: Lance) -> None:
        motivo = self.motivoDeRecusa(lance.valor, lance.dataHora)
        if motivo is not None:
            raise LanceRecusado(motivo, self.explicarRecusa(motivo))
        faltavam = self.dataFimPrevista - lance.dataHora
        self.lances.append(lance)
        if faltavam < JANELA_DE_PRORROGACAO:
            self.dataFimPrevista += PRORROGACAO
