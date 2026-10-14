"""Pacote "Financeiro" do diagrama: Carteira e MovimentacaoCarteira, só para consulta na v2.

Os métodos creditar, debitar, possuiSaldo e solicitarSaque dependem de Transacao e Saque, que
ficaram fora do escopo, e por isso não estão aqui. O lance não usa o saldo da carteira.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(eq=False)
class MovimentacaoCarteira:
    tipo: str
    valor: Decimal
    dataHora: datetime
    descricao: str
    id: int | None = None


@dataclass(eq=False)
class Carteira:
    """Cliente 1 ◆— 1 Carteira; Carteira 1 ◆— 0..* MovimentacaoCarteira."""

    saldo: Decimal = Decimal("0.00")
    movimentacoes: list[MovimentacaoCarteira] = field(default_factory=list)
    id: int | None = None

    def gerarExtrato(self) -> list[MovimentacaoCarteira]:
        """Movimentações da mais recente para a mais antiga."""
        return sorted(self.movimentacoes, key=lambda m: m.dataHora, reverse=True)
