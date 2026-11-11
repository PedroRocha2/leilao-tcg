import sqlite3
from datetime import datetime
from decimal import Decimal

from app.db import de_texto, para_texto
from app.dominio.dinheiro import de_centavos, para_centavos
from app.dominio.loja import ConfiguracaoLoja, LogOperacao


class RepositorioLoja:
    """As configurações da loja (RF15) e o log de auditoria (RF19)."""

    def __init__(self, conexao: sqlite3.Connection):
        self.conexao = conexao

    def configuracao(self) -> ConfiguracaoLoja:
        linha = self.conexao.execute("SELECT * FROM configuracao_loja WHERE id = 1").fetchone()
        if linha is None:
            return ConfiguracaoLoja()
        return ConfiguracaoLoja(
            taxaPercentual=Decimal(linha["taxa_percentual"]),
            incrementoMinimo=de_centavos(linha["incremento_minimo_centavos"]),
            prazoPagamentoHoras=linha["prazo_pagamento_horas"],
            prazoReofertaHoras=linha["prazo_reoferta_horas"],
        )

    def salvar_configuracao(self, configuracao: ConfiguracaoLoja) -> None:
        self.conexao.execute(
            "INSERT INTO configuracao_loja (id, taxa_percentual, incremento_minimo_centavos,"
            " prazo_pagamento_horas, prazo_reoferta_horas) VALUES (1, ?, ?, ?, ?)"
            " ON CONFLICT (id) DO UPDATE SET taxa_percentual = excluded.taxa_percentual,"
            " incremento_minimo_centavos = excluded.incremento_minimo_centavos,"
            " prazo_pagamento_horas = excluded.prazo_pagamento_horas,"
            " prazo_reoferta_horas = excluded.prazo_reoferta_horas",
            (str(configuracao.taxaPercentual), para_centavos(configuracao.incrementoMinimo),
             configuracao.prazoPagamentoHoras, configuracao.prazoReofertaHoras))

    def registrar(self, operacao: str, agora: datetime, usuario_id: int | None = None,
                  valor: Decimal | None = None, ip: str | None = None, detalhe: str = "") -> None:
        self.conexao.execute(
            "INSERT INTO log_operacoes (usuario_id, operacao, valor_centavos, ip, data_hora, detalhe)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (usuario_id, operacao, para_centavos(valor) if valor is not None else None, ip,
             para_texto(agora), detalhe))

    def operacoes(self, limite: int = 300) -> list[LogOperacao]:
        linhas = self.conexao.execute(
            "SELECT l.*, u.nome AS usuario_nome FROM log_operacoes l LEFT JOIN usuarios u ON u.id = l.usuario_id"
            " ORDER BY l.id DESC LIMIT ?", (limite,))
        return [LogOperacao(
            operacao=linha["operacao"], dataHora=de_texto(linha["data_hora"]), usuarioId=linha["usuario_id"],
            usuarioNome=linha["usuario_nome"],
            valor=de_centavos(linha["valor_centavos"]) if linha["valor_centavos"] is not None else None,
            ip=linha["ip"], detalhe=linha["detalhe"], id=linha["id"]) for linha in linhas]
