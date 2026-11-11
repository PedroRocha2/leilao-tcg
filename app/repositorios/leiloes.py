import sqlite3
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from app.db import de_texto, marcadores, para_texto, transacao
from app.dominio.dinheiro import de_centavos, para_centavos
from app.dominio.financeiro import Transacao
from app.dominio.leiloes import Carta, Jogo, Lance, Leilao, StatusLeilao
from app.repositorios.clientes import RepositorioClientes

_ABERTOS = "l.status = 'ativo' AND l.data_inicio <= ? AND l.data_fim_prevista > ?"

# O código da carta é o que a edição traz depois do último parêntese: "Base Set (4/102)" -> "4/102)".
# O nome da coleção fica fora da busca: "dragon" não acha as cartas da "Legend of Blue Eyes White Dragon".
_CODIGO = "substr(c.edicao, length(rtrim(c.edicao, replace(c.edicao, '(', ''))) + 1)"


def _literal(texto: str) -> str:
    """O texto como ele é dentro de um LIKE: % e _ digitados não viram curingas."""
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class RepositorioLeiloes:
    def __init__(self, conexao: sqlite3.Connection, clientes: RepositorioClientes | None = None):
        self.conexao = conexao
        self.clientes = clientes or RepositorioClientes(conexao)

    def jogos(self) -> list[Jogo]:
        return [Jogo(nome=linha["nome"], id=linha["id"])
                for linha in self.conexao.execute("SELECT id, nome FROM jogos ORDER BY nome")]

    def adicionar_jogo(self, jogo: Jogo) -> Jogo:
        jogo.id = self.conexao.execute("INSERT INTO jogos (nome) VALUES (?)", (jogo.nome,)).lastrowid
        return jogo

    def jogo(self, nome: str) -> Jogo:
        """O jogo com este nome; cadastra na primeira carta de um jogo novo."""
        linha = self.conexao.execute("SELECT id, nome FROM jogos WHERE nome = ?", (nome,)).fetchone()
        return Jogo(nome=linha["nome"], id=linha["id"]) if linha else self.adicionar_jogo(Jogo(nome))

    def ativos(self, agora: datetime, jogo_id: int | None = None, texto: str = "") -> list[Leilao]:
        """Os leilões recebendo lances. `texto` busca no nome da carta e no código dela."""
        sql = f"SELECT l.id FROM leiloes l JOIN cartas c ON c.id = l.carta_id WHERE {_ABERTOS}"
        parametros: list = [para_texto(agora)] * 2
        if jogo_id is not None:
            sql += " AND c.jogo_id = ?"
            parametros.append(jogo_id)
        # Cada palavra precisa aparecer no nome ou no código: "dragon 156" acha o Shivan Dragon (156).
        for palavra in texto.split():
            sql += rf" AND (c.nome LIKE ? ESCAPE '\' OR {_CODIGO} LIKE ? ESCAPE '\')"
            parametros += [f"%{_literal(palavra)}%"] * 2
        sql += " ORDER BY l.data_fim_prevista, l.id"
        return self._carregar([linha["id"] for linha in self.conexao.execute(sql, parametros)])

    def ativos_por_jogo(self, agora: datetime) -> dict[int, int]:
        linhas = self.conexao.execute(
            f"""SELECT c.jogo_id, COUNT(*) AS total FROM leiloes l JOIN cartas c ON c.id = l.carta_id
                 WHERE {_ABERTOS} GROUP BY c.jogo_id""",
            [para_texto(agora)] * 2,
        )
        return {linha["jogo_id"]: linha["total"] for linha in linhas}

    def por_id(self, leilao_id: int) -> Leilao | None:
        encontrados = self._carregar([leilao_id])
        return encontrados[0] if encontrados else None

    def outros_do_jogo(self, leilao: Leilao, agora: datetime, limite: int = 4) -> list[Leilao]:
        linhas = self.conexao.execute(
            f"""SELECT l.id FROM leiloes l JOIN cartas c ON c.id = l.carta_id
                 WHERE {_ABERTOS} AND c.jogo_id = ? AND l.id <> ?
                 ORDER BY l.data_fim_prevista, l.id LIMIT ?""",
            [para_texto(agora), para_texto(agora), leilao.carta.jogo.id, leilao.id, limite],
        )
        return self._carregar([linha["id"] for linha in linhas])

    def com_lances_do_cliente(self, cliente_id: int) -> list[Leilao]:
        linhas = self.conexao.execute(
            """SELECT l.id FROM leiloes l
                WHERE l.id IN (SELECT leilao_id FROM lances WHERE cliente_id = ?)
                ORDER BY l.data_fim_prevista DESC, l.id""",
            (cliente_id,),
        )
        return self._carregar([linha["id"] for linha in linhas])

    def vencidos(self, agora: datetime) -> list[Leilao]:
        linhas = self.conexao.execute(
            "SELECT id FROM leiloes WHERE status = 'ativo' AND data_fim_prevista <= ? ORDER BY data_fim_prevista, id",
            (para_texto(agora),),
        )
        return self._carregar([linha["id"] for linha in linhas])

    def a_iniciar(self, agora: datetime) -> list[Leilao]:
        linhas = self.conexao.execute(
            "SELECT id FROM leiloes WHERE status = 'aprovado' AND data_inicio <= ? ORDER BY data_inicio, id",
            (para_texto(agora),),
        )
        return self._carregar([linha["id"] for linha in linhas])

    def pendentes(self) -> list[Leilao]:
        linhas = self.conexao.execute("SELECT id FROM leiloes WHERE status = 'pendente' ORDER BY id")
        return self._carregar([linha["id"] for linha in linhas])

    def do_vendedor(self, cliente_id: int) -> list[Leilao]:
        linhas = self.conexao.execute(
            "SELECT l.id FROM leiloes l JOIN cartas c ON c.id = l.carta_id WHERE c.vendedor_id = ?"
            " ORDER BY l.id DESC",
            (cliente_id,),
        )
        return self._carregar([linha["id"] for linha in linhas])

    def todos(self) -> list[Leilao]:
        return self._carregar([linha["id"] for linha in self.conexao.execute(
            "SELECT id FROM leiloes ORDER BY id DESC")])

    def finalizados(self) -> list[Leilao]:
        """RF16: leilões encerrados ou cancelados, do mais recente para o mais antigo."""
        return self._carregar([linha["id"] for linha in self.conexao.execute(
            "SELECT id FROM leiloes WHERE status IN ('encerrado', 'cancelado')"
            " ORDER BY COALESCE(data_fim_real, data_fim_prevista) DESC, id DESC")])

    def com_transacao(self, status: str | None = None) -> list[Leilao]:
        sql, parametros = "SELECT leilao_id FROM transacoes", []
        if status is not None:
            sql, parametros = sql + " WHERE status = ?", [status]
        return self._carregar([linha["leilao_id"] for linha in self.conexao.execute(
            sql + " ORDER BY data_hora DESC, id DESC", parametros)])

    def por_codigo_de_retirada(self, codigo: str) -> Leilao | None:
        linha = self.conexao.execute(
            "SELECT leilao_id FROM transacoes WHERE codigo_retirada = ?", (codigo.strip().upper(),)).fetchone()
        return self.por_id(linha["leilao_id"]) if linha else None

    def com_pagamento_vencido(self, agora: datetime) -> list[Leilao]:
        linhas = self.conexao.execute(
            "SELECT leilao_id FROM transacoes WHERE status = 'aguardando pagamento' AND prazo_pagamento <= ?"
            " ORDER BY prazo_pagamento, id", (para_texto(agora),))
        return self._carregar([linha["leilao_id"] for linha in linhas])

    def arrematados_por(self, cliente_id: int) -> list[Leilao]:
        linhas = self.conexao.execute(
            "SELECT leilao_id FROM transacoes WHERE comprador_id = ? ORDER BY data_hora DESC, id DESC",
            (cliente_id,),
        )
        return self._carregar([linha["leilao_id"] for linha in linhas])

    def _carregar(self, ids: list[int]) -> list[Leilao]:
        if not ids:
            return []
        marcas = marcadores(len(ids))
        leiloes = {linha["id"]: linha for linha in self.conexao.execute(
            f"SELECT * FROM leiloes WHERE id IN ({marcas})", ids)}
        carta_ids = sorted({linha["carta_id"] for linha in leiloes.values()})
        cartas = {linha["id"]: linha for linha in self.conexao.execute(
            f"""SELECT c.*, j.nome AS jogo_nome FROM cartas c JOIN jogos j ON j.id = c.jogo_id
                 WHERE c.id IN ({marcadores(len(carta_ids))})""", carta_ids)}
        fotos = defaultdict(list)
        for linha in self.conexao.execute(
            f"SELECT carta_id, url FROM carta_fotos WHERE carta_id IN ({marcadores(len(carta_ids))})"
            " ORDER BY carta_id, ordem", carta_ids,
        ):
            fotos[linha["carta_id"]].append(linha["url"])
        lances = defaultdict(list)
        for linha in self.conexao.execute(
            f"SELECT * FROM lances WHERE leilao_id IN ({marcas}) ORDER BY data_hora, id", ids
        ):
            lances[linha["leilao_id"]].append(linha)
        transacoes = {linha["leilao_id"]: linha for linha in self.conexao.execute(
            f"SELECT * FROM transacoes WHERE leilao_id IN ({marcas})", ids)}

        clientes = self.clientes.carregar(
            [linha["vendedor_id"] for linha in cartas.values()]
            + [lance["cliente_id"] for grupo in lances.values() for lance in grupo]
            + [linha["comprador_id"] for linha in transacoes.values()]
        )
        jogos: dict[int, Jogo] = {}
        resultado = []
        for leilao_id in ids:
            linha = leiloes.get(leilao_id)
            if linha is None:
                continue
            dados_carta = cartas[linha["carta_id"]]
            jogo = jogos.setdefault(dados_carta["jogo_id"], Jogo(nome=dados_carta["jogo_nome"], id=dados_carta["jogo_id"]))
            carta = Carta(
                nome=dados_carta["nome"], jogo=jogo, edicao=dados_carta["edicao"],
                condicao=dados_carta["condicao"], descricao=dados_carta["descricao"],
                vendedor=clientes[dados_carta["vendedor_id"]], status=dados_carta["status"],
                id=dados_carta["id"],
            )
            for url in fotos[carta.id]:
                carta.adicionarFoto(url)
            arremate = transacoes.get(leilao_id)
            resultado.append(Leilao(
                carta=carta,
                lanceInicial=de_centavos(linha["lance_inicial_centavos"]),
                incrementoMinimo=de_centavos(linha["incremento_minimo_centavos"]),
                dataInicio=de_texto(linha["data_inicio"]),
                dataFimPrevista=de_texto(linha["data_fim_prevista"]),
                dataFimReal=de_texto(linha["data_fim_real"]) if linha["data_fim_real"] else None,
                status=StatusLeilao(linha["status"]),
                lances=[
                    Lance(valor=de_centavos(lance["valor_centavos"]), dataHora=de_texto(lance["data_hora"]),
                          cliente=clientes[lance["cliente_id"]], id=lance["id"])
                    for lance in lances[leilao_id]
                ],
                transacao=self._transacao(arremate, clientes, carta) if arremate else None,
                taxaPercentual=Decimal(linha["taxa_percentual"]),
                motivoRecusa=linha["motivo_recusa"],
                id=leilao_id,
            ))
        return resultado

    @staticmethod
    def _transacao(linha, clientes, carta: Carta) -> Transacao:
        def momento(coluna):
            return de_texto(linha[coluna]) if linha[coluna] else None

        return Transacao(
            valor=de_centavos(linha["valor_centavos"]), dataHora=de_texto(linha["data_hora"]),
            comprador=clientes[linha["comprador_id"]], vendedor=carta.vendedor,
            prazoPagamento=de_texto(linha["prazo_pagamento"]), taxa=de_centavos(linha["taxa_centavos"]),
            status=linha["status"], codigoRetirada=linha["codigo_retirada"],
            dataPagamento=momento("data_pagamento"), dataEntrega=momento("data_entrega"),
            pagoComSaldo=de_centavos(linha["pago_saldo_centavos"]),
            pagoNoGateway=de_centavos(linha["pago_gateway_centavos"]),
            formaDePagamento=linha["forma_pagamento"], id=linha["id"],
        )

    def adicionar(self, leilao: Leilao) -> Leilao:
        carta = leilao.carta
        with transacao(self.conexao):
            carta.id = self.conexao.execute(
                "INSERT INTO cartas (jogo_id, vendedor_id, nome, edicao, condicao, descricao, status)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (carta.jogo.id, carta.vendedor.id, carta.nome, carta.edicao, carta.condicao,
                 carta.descricao, carta.status),
            ).lastrowid
            self.conexao.executemany(
                "INSERT INTO carta_fotos (carta_id, ordem, url) VALUES (?, ?, ?)",
                [(carta.id, ordem, url) for ordem, url in enumerate(carta.fotos, start=1)],
            )
            leilao.id = self.conexao.execute(
                "INSERT INTO leiloes (carta_id, lance_inicial_centavos, incremento_minimo_centavos,"
                " data_inicio, data_fim_prevista, data_fim_real, status, taxa_percentual)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (carta.id, para_centavos(leilao.lanceInicial), para_centavos(leilao.incrementoMinimo),
                 para_texto(leilao.dataInicio), para_texto(leilao.dataFimPrevista),
                 para_texto(leilao.dataFimReal) if leilao.dataFimReal else None, str(leilao.status),
                 str(leilao.taxaPercentual)),
            ).lastrowid
            for lance in leilao.lances:
                self._inserir_lance(leilao, lance)
        return leilao

    def salvar_lance(self, leilao: Leilao, lance: Lance) -> None:
        with transacao(self.conexao):
            self._inserir_lance(leilao, lance)
            self.conexao.execute(
                "UPDATE leiloes SET data_fim_prevista = ? WHERE id = ?",
                (para_texto(leilao.dataFimPrevista), leilao.id),
            )

    def salvar_status(self, leilao: Leilao) -> None:
        with transacao(self.conexao):
            self.conexao.execute(
                "UPDATE leiloes SET status = ?, data_fim_real = ?, motivo_recusa = ? WHERE id = ?",
                (str(leilao.status), para_texto(leilao.dataFimReal) if leilao.dataFimReal else None,
                 leilao.motivoRecusa, leilao.id),
            )
            self.conexao.execute(
                "UPDATE cartas SET status = ? WHERE id = ?", (str(leilao.carta.status), leilao.carta.id)
            )

    def salvar_encerramento(self, leilao: Leilao) -> None:
        arremate = leilao.transacao
        with transacao(self.conexao):
            self.salvar_status(leilao)
            if arremate is not None:
                arremate.id = self.conexao.execute(
                    "INSERT INTO transacoes (leilao_id, comprador_id, valor_centavos, data_hora, status,"
                    " taxa_centavos, liquido_centavos, codigo_retirada, prazo_pagamento)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (leilao.id, arremate.comprador.id, para_centavos(arremate.valor),
                     para_texto(arremate.dataHora), str(arremate.status), para_centavos(arremate.taxa),
                     para_centavos(arremate.valorLiquido), arremate.codigoRetirada,
                     para_texto(arremate.prazoPagamento)),
                ).lastrowid

    def salvar_transacao(self, leilao: Leilao) -> None:
        """Grava o andamento do arremate (pagamento, entrega, expiração) e o status da carta."""
        arremate = leilao.transacao
        with transacao(self.conexao):
            self.conexao.execute(
                "UPDATE transacoes SET status = ?, data_pagamento = ?, data_entrega = ?,"
                " pago_saldo_centavos = ?, pago_gateway_centavos = ?, forma_pagamento = ? WHERE id = ?",
                (str(arremate.status),
                 para_texto(arremate.dataPagamento) if arremate.dataPagamento else None,
                 para_texto(arremate.dataEntrega) if arremate.dataEntrega else None,
                 para_centavos(arremate.pagoComSaldo), para_centavos(arremate.pagoNoGateway),
                 arremate.formaDePagamento, arremate.id))
            self.conexao.execute(
                "UPDATE cartas SET status = ? WHERE id = ?", (str(leilao.carta.status), leilao.carta.id))

    def salvar_carta(self, carta: Carta) -> None:
        """RF04: grava os dados da carta que o administrador corrigiu."""
        self.conexao.execute(
            "UPDATE cartas SET nome = ?, jogo_id = ?, edicao = ?, condicao = ? WHERE id = ?",
            (carta.nome, carta.jogo.id, carta.edicao, carta.condicao, carta.id))

    def remover(self, leilao: Leilao) -> None:
        """RF04: apaga o cadastro da carta e o leilão dela. Só serve para leilão sem lances."""
        with transacao(self.conexao):
            self.conexao.execute("DELETE FROM leiloes WHERE id = ?", (leilao.id,))
            self.conexao.execute("DELETE FROM cartas WHERE id = ?", (leilao.carta.id,))

    def _inserir_lance(self, leilao: Leilao, lance: Lance) -> None:
        self.conexao.execute(
            "INSERT INTO lances (leilao_id, cliente_id, valor_centavos, data_hora) VALUES (?, ?, ?, ?)",
            (leilao.id, lance.cliente.id, para_centavos(lance.valor), para_texto(lance.dataHora)),
        )
