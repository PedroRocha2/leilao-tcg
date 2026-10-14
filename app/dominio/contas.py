"""Pacote "Contas e Acesso" do diagrama: Usuario (abstrata) e Cliente.

Administrador ficou fora do escopo da v2. Também ficaram fora alterarSenha, atualizarPerfil e
desativar (não há telas para eles) e os métodos de Cliente que dependem de Transacao e Pagamento.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

from app.dominio import senhas
from app.dominio.dinheiro import reais
from app.dominio.financeiro import Carteira
from app.dominio.leiloes import Lance, LanceRecusado, Leilao, MotivoRecusa


@dataclass(kw_only=True, eq=False)
class Usuario(ABC):
    """Classe abstrata: só as subclasses (Cliente) são instanciadas."""

    nome: str
    email: str
    senhaHash: str
    telefone: str
    dataCadastro: date
    ativo: bool = True
    id: int | None = None

    def __new__(cls, *args, **kwargs):
        if cls is Usuario:
            raise TypeError("Usuario é uma classe abstrata: crie um Cliente.")
        return super().__new__(cls)

    def autenticar(self, senha: str) -> bool:
        """Confere a senha com o senhaHash. Conta desativada não autentica."""
        return self.ativo and senhas.conferir(senha, self.senhaHash)

    def ehOMesmo(self, outro: Usuario) -> bool:
        """Auxiliar: mesma pessoa, ainda que carregada do banco em objetos diferentes."""
        return self is outro or (self.id is not None and self.id == outro.id)


@dataclass(kw_only=True, eq=False)
class Cliente(Usuario):
    """Cliente 1 ◆— 1 Carteira: a carteira nasce com o cliente, com saldo 0."""

    cpf: str
    bloqueado: bool = False
    descumprimentos: int = 0
    carteira: Carteira = field(default_factory=Carteira)

    def podeDarLance(self) -> bool:
        """RN15: conta bloqueada (ou desativada) não dá lance. O saldo da carteira não entra."""
        return self.ativo and not self.bloqueado

    def darLance(self, leilao: Leilao, valor: Decimal, agora: datetime | None = None) -> Lance:
        """RF07: registra o lance no leilão e devolve o Lance criado.

        Levanta LanceRecusado com o motivo quando alguma regra impede o lance.
        """
        if not self.podeDarLance():
            mensagem = ("Sua conta está bloqueada para lances. Fale com a loja para regularizar."
                        if self.ativo else "Sua conta está desativada e não pode dar lances.")
            raise LanceRecusado(MotivoRecusa.CLIENTE_BLOQUEADO, mensagem)
        if leilao.carta.vendedor.ehOMesmo(self):  # RN11
            raise LanceRecusado(
                MotivoRecusa.PROPRIO_LEILAO,
                "Você é o vendedor desta carta e não pode dar lances no próprio leilão.",
            )
        lance = Lance(valor=reais(valor), dataHora=agora or datetime.now(UTC), cliente=self)
        leilao.receberLance(lance)
        return lance
