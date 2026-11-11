import sqlite3
from collections import defaultdict
from datetime import date

from app.db import de_texto, marcadores, para_texto, transacao
from app.dominio.contas import Administrador, Cliente, Usuario
from app.dominio.dinheiro import de_centavos, para_centavos
from app.dominio.financeiro import Carteira, MovimentacaoCarteira, Saque

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
        with transacao(self.conexao):
            self._inserir_usuario(cliente)
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

    def adicionar_administrador(self, administrador: Administrador) -> Administrador:
        with transacao(self.conexao):
            self._inserir_usuario(administrador)
            self.conexao.execute("INSERT INTO administradores (usuario_id) VALUES (?)", (administrador.id,))
        return administrador

    def _inserir_usuario(self, usuario: Usuario) -> None:
        usuario.id = self.conexao.execute(
            "INSERT INTO usuarios (nome, email, senha_hash, telefone, data_cadastro, ativo)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (usuario.nome, usuario.email, usuario.senhaHash, usuario.telefone,
             usuario.dataCadastro.isoformat(), int(usuario.ativo)),
        ).lastrowid

    def email_em_uso(self, email: str, exceto: int | None = None) -> bool:
        linha = self.conexao.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()
        return linha is not None and linha["id"] != exceto

    def cpf_em_uso(self, cpf: str) -> bool:
        return self.conexao.execute("SELECT 1 FROM clientes WHERE cpf = ?", (cpf,)).fetchone() is not None

    def por_id(self, cliente_id: int) -> Cliente | None:
        return self.carregar([cliente_id]).get(cliente_id)

    def por_email(self, email: str) -> Cliente | None:
        linha = self.conexao.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()
        return self.por_id(linha["id"]) if linha else None

    def usuario_por_id(self, usuario_id: int) -> Usuario | None:
        """O cliente ou o administrador com este id."""
        return self.por_id(usuario_id) or self._administrador(usuario_id)

    def usuario_por_login(self, login: str) -> Usuario | None:
        """Quem entra com este e-mail (cliente) ou nome de usuário (administrador)."""
        linha = self.conexao.execute("SELECT id FROM usuarios WHERE email = ?", (login,)).fetchone()
        return self.usuario_por_id(linha["id"]) if linha else None

    def _administrador(self, usuario_id: int) -> Administrador | None:
        linha = self.conexao.execute(
            "SELECT u.* FROM usuarios u JOIN administradores a ON a.usuario_id = u.id WHERE u.id = ?",
            (usuario_id,)).fetchone()
        if linha is None:
            return None
        return Administrador(
            id=linha["id"], nome=linha["nome"], email=linha["email"], senhaHash=linha["senha_hash"],
            telefone=linha["telefone"], dataCadastro=date.fromisoformat(linha["data_cadastro"]),
            ativo=bool(linha["ativo"]))

    def todos(self) -> list[Cliente]:
        ids = [linha["usuario_id"] for linha in self.conexao.execute("SELECT usuario_id FROM clientes")]
        return sorted(self.carregar(ids).values(), key=lambda cliente: cliente.nome.casefold())

    def carregar(self, ids) -> dict[int, Cliente]:
        ids = sorted(set(ids))
        if not ids:
            return {}
        marcas = marcadores(len(ids))
        linhas = self.conexao.execute(_SELECT_CLIENTE + f" WHERE u.id IN ({marcas})", ids).fetchall()
        carteiras = {
            linha["cliente_id"]: linha
            for linha in self.conexao.execute(
                f"SELECT * FROM carteiras WHERE cliente_id IN ({marcas})", ids)
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
        saques = defaultdict(list)
        for linha in self.conexao.execute(
            f"""SELECT s.*, c.cliente_id FROM saques s JOIN carteiras c ON c.id = s.carteira_id
                 WHERE c.cliente_id IN ({marcas}) ORDER BY s.data_solicitacao, s.id""",
            ids,
        ):
            saques[linha["cliente_id"]].append(Saque(
                valor=de_centavos(linha["valor_centavos"]), chavePix=linha["chave_pix"],
                dataSolicitacao=de_texto(linha["data_solicitacao"]), status=linha["status"],
                dataResposta=de_texto(linha["data_resposta"]) if linha["data_resposta"] else None,
                id=linha["id"],
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
                                  bloqueado=de_centavos(carteira["bloqueado_centavos"]),
                                  movimentacoes=movimentacoes[linha["id"]], saques=saques[linha["id"]],
                                  id=carteira["id"]),
            )
        return clientes

    def atualizar(self, cliente: Cliente) -> None:
        """Grava os dados de cadastro, o bloqueio e os descumprimentos do cliente."""
        with transacao(self.conexao):
            self.conexao.execute(
                "UPDATE usuarios SET nome = ?, email = ?, telefone = ?, ativo = ? WHERE id = ?",
                (cliente.nome, cliente.email, cliente.telefone, int(cliente.ativo), cliente.id))
            self.conexao.execute(
                "UPDATE clientes SET bloqueado = ?, descumprimentos = ? WHERE usuario_id = ?",
                (int(cliente.bloqueado), cliente.descumprimentos, cliente.id))

    def salvar_carteira(self, cliente: Cliente) -> None:
        """Grava o saldo, o valor bloqueado e o que ainda não foi gravado de movimentações e saques."""
        carteira = cliente.carteira
        with transacao(self.conexao):
            self.conexao.execute(
                "UPDATE carteiras SET saldo_centavos = ?, bloqueado_centavos = ? WHERE id = ?",
                (para_centavos(carteira.saldo), para_centavos(carteira.bloqueado), carteira.id))
            for movimentacao in carteira.movimentacoes:
                if movimentacao.id is None:
                    movimentacao.id = self.conexao.execute(
                        "INSERT INTO movimentacoes_carteira (carteira_id, tipo, valor_centavos, data_hora,"
                        " descricao) VALUES (?, ?, ?, ?, ?)",
                        (carteira.id, movimentacao.tipo, para_centavos(movimentacao.valor),
                         para_texto(movimentacao.dataHora), movimentacao.descricao)).lastrowid
            for saque in carteira.saques:
                resposta = para_texto(saque.dataResposta) if saque.dataResposta else None
                if saque.id is None:
                    saque.id = self.conexao.execute(
                        "INSERT INTO saques (carteira_id, valor_centavos, chave_pix, data_solicitacao, status,"
                        " data_resposta) VALUES (?, ?, ?, ?, ?, ?)",
                        (carteira.id, para_centavos(saque.valor), saque.chavePix,
                         para_texto(saque.dataSolicitacao), str(saque.status), resposta)).lastrowid
                else:
                    self.conexao.execute("UPDATE saques SET status = ?, data_resposta = ? WHERE id = ?",
                                         (str(saque.status), resposta, saque.id))

    def saques(self) -> list[tuple[Saque, Cliente]]:
        """Todos os saques com o cliente de cada um, do mais recente para o mais antigo."""
        clientes = self.carregar(
            linha["cliente_id"] for linha in self.conexao.execute(
                "SELECT DISTINCT c.cliente_id FROM saques s JOIN carteiras c ON c.id = s.carteira_id"))
        pares = [(saque, cliente) for cliente in clientes.values() for saque in cliente.carteira.saques]
        return sorted(pares, key=lambda par: (par[0].dataSolicitacao, par[0].id), reverse=True)
