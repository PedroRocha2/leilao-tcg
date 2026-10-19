from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(eq=False)
class MovimentacaoCarteira:
    """Registro de transação financeira na carteira do cliente."""
    tipo: str
    valor: Decimal
    dataHora: datetime
    descricao: str
    id: int | None = None


@dataclass(eq=False)
class Carteira:
    """Representa a carteira virtual e saldo disponível do cliente."""
    saldo: Decimal = Decimal("0.00")
    movimentacoes: list[MovimentacaoCarteira] = field(default_factory=list)
    id: int | None = None

    def gerarExtrato(self) -> list[MovimentacaoCarteira]:
        """Retorna o histórico de movimentações em ordem cronológica decrescente."""
        return sorted(self.movimentacoes, key=lambda m: m.dataHora, reverse=True)
