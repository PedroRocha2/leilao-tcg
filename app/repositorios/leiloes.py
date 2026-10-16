import sqlite3
from collections import defaultdict
from datetime import datetime

from app.db import de_texto, marcadores, para_texto, transacao
from app.dominio.dinheiro import de_centavos, para_centavos
from app.dominio.leiloes import Carta, Jogo, Lance, Leilao, StatusLeilao
from app.repositorios.clientes import RepositorioClientes

_ABERTOS = "l.status = 'ativo' AND l.data_inicio <= ? AND l.data_fim_prevista > ?"


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

    def ativos(self, agora: datetime, jogo_id: int | None = None) -> list[Leilao]:
        sql = f"SELECT l.id FROM leiloes l JOIN cartas c ON c.id = l.carta_id WHERE {_ABERTOS}"
        parametros: list = [para_texto(agora)] * 2
        if jogo_id is not None:
            sql += " AND c.jogo_id = ?"
            parametros.append(jogo_id)
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

        clientes = self.clientes.carregar(
            [linha["vendedor_id"] for linha in cartas.values()]
            + [lance["cliente_id"] for grupo in lances.values() for lance in grupo]
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
                id=leilao_id,
            ))
        return resultado

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
                " data_inicio, data_fim_prevista, data_fim_real, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (carta.id, para_centavos(leilao.lanceInicial), para_centavos(leilao.incrementoMinimo),
                 para_texto(leilao.dataInicio), para_texto(leilao.dataFimPrevista),
                 para_texto(leilao.dataFimReal) if leilao.dataFimReal else None, str(leilao.status)),
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

    def _inserir_lance(self, leilao: Leilao, lance: Lance) -> None:
        self.conexao.execute(
            "INSERT INTO lances (leilao_id, cliente_id, valor_centavos, data_hora) VALUES (?, ?, ?, ?)",
            (leilao.id, lance.cliente.id, para_centavos(lance.valor), para_texto(lance.dataHora)),
        )
