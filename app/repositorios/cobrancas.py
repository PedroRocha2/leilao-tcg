import sqlite3
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.db import de_texto, para_texto
from app.dominio.dinheiro import de_centavos, para_centavos
from app.dominio.financeiro import ZERO


class StatusCobranca(StrEnum):
    PENDENTE = "pendente"
    PAGA = "paga"
    # Pago, mas não quitou o arremate: o valor foi para a carteira.
    CREDITADA = "creditada"


@dataclass(eq=False)
class Cobranca:
    """RF11. `comSaldo` sai da carteira só na confirmação (RN18)."""
    leilaoId: int
    referencia: str
    valor: Decimal
    checkoutId: str
    checkoutUrl: str
    dataCriacao: datetime
    comSaldo: Decimal = ZERO
    status: str = StatusCobranca.PENDENTE
    pagamentoId: str | None = None
    dataResposta: datetime | None = None
    id: int | None = None


class RepositorioCobrancas:
    def __init__(self, conexao: sqlite3.Connection):
        self.conexao = conexao

    def adicionar(self, cobranca: Cobranca) -> Cobranca:
        cobranca.id = self.conexao.execute(
            "INSERT INTO cobrancas (leilao_id, referencia, valor_centavos, saldo_centavos, checkout_id,"
            " checkout_url, status, data_criacao) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (cobranca.leilaoId, cobranca.referencia, para_centavos(cobranca.valor),
             para_centavos(cobranca.comSaldo), cobranca.checkoutId, cobranca.checkoutUrl, str(cobranca.status),
             para_texto(cobranca.dataCriacao))).lastrowid
        return cobranca

    def salvar(self, cobranca: Cobranca) -> None:
        self.conexao.execute(
            "UPDATE cobrancas SET status = ?, pagamento_id = ?, data_resposta = ? WHERE id = ?",
            (str(cobranca.status), cobranca.pagamentoId,
             para_texto(cobranca.dataResposta) if cobranca.dataResposta else None, cobranca.id))

    def por_referencia(self, referencia: str) -> Cobranca | None:
        linha = self.conexao.execute("SELECT * FROM cobrancas WHERE referencia = ?", (referencia,)).fetchone()
        return self._cobranca(linha) if linha else None

    def pendentes_do_leilao(self, leilao_id: int) -> list[Cobranca]:
        linhas = self.conexao.execute(
            "SELECT * FROM cobrancas WHERE leilao_id = ? AND status = 'pendente' ORDER BY id DESC", (leilao_id,))
        return [self._cobranca(linha) for linha in linhas]

    @staticmethod
    def _cobranca(linha) -> Cobranca:
        return Cobranca(
            leilaoId=linha["leilao_id"], referencia=linha["referencia"],
            valor=de_centavos(linha["valor_centavos"]), comSaldo=de_centavos(linha["saldo_centavos"]),
            checkoutId=linha["checkout_id"], checkoutUrl=linha["checkout_url"],
            status=StatusCobranca(linha["status"]), pagamentoId=linha["pagamento_id"],
            dataCriacao=de_texto(linha["data_criacao"]),
            dataResposta=de_texto(linha["data_resposta"]) if linha["data_resposta"] else None, id=linha["id"])
