from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from app.dominio.dinheiro import formatar_reais, reais
from app.dominio.financeiro import Transacao

if TYPE_CHECKING:
    from app.dominio.contas import Cliente

JANELA_DE_PRORROGACAO = timedelta(minutes=3)
PRORROGACAO = timedelta(minutes=3)
# Valores iniciais da loja; o lojista muda nas configurações (RF15). RN17: valem como estavam quando o
# leilão foi criado, por isso ficam gravados em cada leilão.
INCREMENTO_DA_LOJA = Decimal("5.00")
TAXA_DA_LOJA = Decimal("10.00")
PRAZO_DE_PAGAMENTO = timedelta(hours=48)
CONDICOES = ("Near Mint (NM)", "Lightly Played (LP)", "Moderately Played (MP)", "Heavily Played (HP)",
             "Damaged (DMG)")


class StatusLeilao(StrEnum):
    PENDENTE = "pendente"
    APROVADO = "aprovado"
    ATIVO = "ativo"
    ENCERRADO = "encerrado"
    CANCELADO = "cancelado"


class StatusCarta(StrEnum):
    """Os status do RF14 que já têm fluxo implementado."""
    AGUARDANDO_DEPOSITO = "aguardando depósito"
    RECUSADA = "recusada"
    APROVADA = "aprovada"
    EM_LEILAO = "em leilão"
    ARREMATADA = "arrematada"
    DEVOLVIDA_AO_VENDEDOR = "devolvida ao vendedor"
    PAGA = "paga"
    ENTREGUE = "entregue"


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

    def atualizarStatus(self, status: str) -> None:
        self.status = status


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
    transacao: Transacao | None = None
    taxaPercentual: Decimal = TAXA_DA_LOJA
    motivoRecusa: str | None = None
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
        if motivo is MotivoRecusa.LEILAO_INATIVO and self.status == StatusLeilao.ENCERRADO:
            return ("Este leilão já foi encerrado e não recebe mais lances. "
                    "Escolha outro na lista de leilões ativos.")
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

    def aprovar(self, agora: datetime | None = None) -> None:
        """RN12: a loja recebeu a carta em depósito e aprovou o leilão."""
        agora = agora or datetime.now(UTC)
        if self.status != StatusLeilao.PENDENTE:
            raise ValueError("Só um leilão que aguarda aprovação pode ser aprovado.")
        if agora >= self.dataFimPrevista:
            raise ValueError("O fim previsto deste leilão já passou; ele não pode mais ser aprovado.")
        self.status = StatusLeilao.APROVADO
        self.carta.atualizarStatus(StatusCarta.APROVADA)

    def recusar(self, motivo: str) -> None:
        """RF05: a loja conferiu a carta e recusou o leilão. O motivo fica registrado para o vendedor."""
        if self.status != StatusLeilao.PENDENTE:
            raise ValueError("Só um leilão que aguarda aprovação pode ser recusado.")
        if not (motivo or "").strip():
            raise ValueError("Informe o motivo da recusa.")
        self.status = StatusLeilao.CANCELADO
        self.motivoRecusa = motivo.strip()
        self.carta.atualizarStatus(StatusCarta.RECUSADA)

    def iniciar(self, agora: datetime | None = None) -> None:
        """RN12: o leilão aprovado entra em andamento quando a data de início chega."""
        agora = agora or datetime.now(UTC)
        if self.status != StatusLeilao.APROVADO:
            raise ValueError("Só um leilão aprovado pode ser iniciado.")
        if agora < self.dataInicio:
            raise ValueError("A data de início deste leilão ainda não chegou.")
        self.status = StatusLeilao.ATIVO
        self.carta.atualizarStatus(StatusCarta.EM_LEILAO)

    def encerrar(self, agora: datetime | None = None,
                 prazoDePagamento: timedelta = PRAZO_DE_PAGAMENTO) -> Transacao | None:
        """Encerra o leilão cujo prazo terminou e gera o arremate para o maior lance, se houver.

        O arremate já sai com a taxa da loja e o valor líquido do vendedor (RF13), o código de retirada
        (RF10) e o prazo de pagamento (RN06).
        """
        agora = agora or datetime.now(UTC)
        if self.status != StatusLeilao.ATIVO:
            raise ValueError("Só um leilão ativo pode ser encerrado.")
        if agora < self.dataFimPrevista:
            raise ValueError("O prazo deste leilão ainda não terminou.")
        # O leilão termina no fim do prazo, não no instante em que o sistema processa o encerramento.
        self.status = StatusLeilao.ENCERRADO
        self.dataFimReal = self.dataFimPrevista
        vencedor = self.getMaiorLance()
        if vencedor is None:
            self.carta.atualizarStatus(StatusCarta.DEVOLVIDA_AO_VENDEDOR)
            return None
        self.carta.atualizarStatus(StatusCarta.ARREMATADA)
        self.transacao = Transacao(
            valor=vencedor.valor, dataHora=self.dataFimReal, comprador=vencedor.cliente,
            vendedor=self.carta.vendedor, prazoPagamento=self.dataFimReal + prazoDePagamento,
            taxa=reais(vencedor.valor * self.taxaPercentual / 100))
        return self.transacao
