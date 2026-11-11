from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from app.dominio.leiloes import INCREMENTO_DA_LOJA, PRAZO_DE_PAGAMENTO, TAXA_DA_LOJA


@dataclass(eq=False)
class ConfiguracaoLoja:
    """RF15: o que o lojista configura. Taxa e incremento valem para os leilões criados depois (RN17)."""
    taxaPercentual: Decimal = TAXA_DA_LOJA
    incrementoMinimo: Decimal = INCREMENTO_DA_LOJA
    prazoPagamentoHoras: int = int(PRAZO_DE_PAGAMENTO.total_seconds() // 3600)
    prazoReofertaHoras: int = 24

    def __post_init__(self):
        if not Decimal("0") <= self.taxaPercentual < Decimal("100"):
            raise ValueError("A taxa da loja precisa ficar entre 0% e 100%.")
        if self.incrementoMinimo <= 0:
            raise ValueError("O incremento mínimo precisa ser maior que zero.")
        if self.prazoPagamentoHoras <= 0 or self.prazoReofertaHoras <= 0:
            raise ValueError("Os prazos precisam ser de pelo menos 1 hora.")

    @property
    def prazoDePagamento(self) -> timedelta:
        return timedelta(hours=self.prazoPagamentoHoras)


@dataclass(frozen=True)
class LogOperacao:
    """RF19: uma linha do log de auditoria. Sem usuário quando a operação é do próprio sistema."""
    operacao: str
    dataHora: datetime
    usuarioId: int | None = None
    usuarioNome: str | None = None
    valor: Decimal | None = None
    ip: str | None = None
    detalhe: str = ""
    id: int | None = None
