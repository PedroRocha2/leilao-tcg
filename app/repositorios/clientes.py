"""Cliente com o Usuario (herança) e a Carteira composta, que nasce e é lida junto com ele."""

import sqlite3
from collections import defaultdict
from datetime import date

from app.db import de_texto, marcadores, transacao
from app.dominio.contas import Cliente
from app.dominio.dinheiro import de_centavos, para_centavos
from app.dominio.financeiro import Carteira, MovimentacaoCarteira

_SELECT_CLIENTE = """
    SELECT u.id, u.nome, u.email, u.senha_hash, u.telefone, u.data_cadastro, u.ativo,
           c.cpf, c.bloqueado, c.descumprimentos
      FROM usuarios u
      JOIN clientes c ON c.usuario_id = u.id
"""


class RepositorioClientes:
    def __init__(self, conexao: sqlite3.Connection):
        self.conexao = conexao

    def adicionar(self, cliente: Cliente) -> Cliente:
        """Grava Usuario, Cliente e Carteira numa transação: não existe cliente sem carteira."""
        with transacao(self.conexao):
            cursor = self.conexao.execute(
                "INSERT INTO usuarios (nome, email, senha_hash, telefone, data_cadastro, ativo)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (cliente.nome, cliente.email, cliente.senhaHash, cliente.telefone,
                 cliente.dataCadastro.isoformat(), int(cliente.ativo)),
            )
            cliente.id = cursor.lastrowid
            self.conexao.execute(
                "INSERT INTO clientes (usuario_id, cpf, bloqueado, descumprimentos) VALUES (?, ?, ?, ?)",
                (cliente.id, cliente.cpf, int(cliente.bloqueado), cliente.descumprimentos),
            )
            cursor = self.conexao.execute(
                "INSERT INTO carteiras (cliente_id, saldo_centavos) VALUES (?, ?)",
                (cliente.id, para_centavos(cliente.carteira.saldo)),
            )
            cliente.carteira.id = cursor.lastrowid
        return cliente

    def email_em_uso(self, email: str) -> bool:
        # A coluna usa COLLATE NOCASE: "Ana@X.com" e "ana@x.com" são o mesmo e-mail.
        return self.conexao.execute("SELECT 1 FROM usuarios WHERE email = ?", (email,)).fetchone() is not None

    def cpf_em_uso(self, cpf: str) -> bool:
        return self.conexao.execute("SELECT 1 FROM clientes WHERE cpf = ?", (cpf,)).fetchone() is not None

    def por_id(self, cliente_id: int) -> Cliente | None:
        return self.carregar([cliente_id]).get(cliente_id)

    def por_email(self, email: str) -> Cliente | None:
        linha = self.conexao.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()
        return self.por_id(linha["id"]) if linha else None

    def carregar(self, ids) -> dict[int, Cliente]:
        """Monta vários clientes de uma vez (três consultas, qualquer que seja a quantidade)."""
        ids = sorted(set(ids))
        if not ids:
            return {}
        marcas = marcadores(len(ids))
        linhas = self.conexao.execute(_SELECT_CLIENTE + f" WHERE u.id IN ({marcas})", ids).fetchall()
        carteiras = {
            linha["cliente_id"]: linha
            for linha in self.conexao.execute(
                f"SELECT id, cliente_id, saldo_centavos FROM carteiras WHERE cliente_id IN ({marcas})", ids
            )
        }
        movimentacoes = defaultdict(list)
        for linha in self.conexao.execute(
            f"""SELECT m.id, m.tipo, m.valor_centavos, m.data_hora, m.descricao, c.cliente_id
                  FROM movimentacoes_carteira m JOIN carteiras c ON c.id = m.carteira_id
                 WHERE c.cliente_id IN ({marcas}) ORDER BY m.data_hora, m.id""",
            ids,
        ):
            movimentacoes[linha["cliente_id"]].append(MovimentacaoCarteira(
                tipo=linha["tipo"], valor=de_centavos(linha["valor_centavos"]),
                dataHora=de_texto(linha["data_hora"]), descricao=linha["descricao"], id=linha["id"],
            ))

        clientes = {}
        for linha in linhas:
            carteira = carteiras[linha["id"]]
            clientes[linha["id"]] = Cliente(
                id=linha["id"], nome=linha["nome"], email=linha["email"], senhaHash=linha["senha_hash"],
                telefone=linha["telefone"], dataCadastro=date.fromisoformat(linha["data_cadastro"]),
                ativo=bool(linha["ativo"]), cpf=linha["cpf"], bloqueado=bool(linha["bloqueado"]),
                descumprimentos=linha["descumprimentos"],
                carteira=Carteira(saldo=de_centavos(carteira["saldo_centavos"]),
                                  movimentacoes=movimentacoes[linha["id"]], id=carteira["id"]),
            )
        return clientes
