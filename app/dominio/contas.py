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
        return self.ativo and senhas.conferir(senha, self.senhaHash)

    def ehOMesmo(self, outro: Usuario) -> bool:
        return self is outro or (self.id is not None and self.id == outro.id)


@dataclass(kw_only=True, eq=False)
class Cliente(Usuario):
    cpf: str
    bloqueado: bool = False
    descumprimentos: int = 0
    carteira: Carteira = field(default_factory=Carteira)

    def podeDarLance(self) -> bool:
        return self.ativo and not self.bloqueado

    def darLance(self, leilao: Leilao, valor: Decimal, agora: datetime | None = None) -> Lance:
        if not self.podeDarLance():
            mensagem = ("Sua conta está bloqueada para lances. Fale com a loja para regularizar."
                        if self.ativo else "Sua conta está desativada e não pode dar lances.")
            raise LanceRecusado(MotivoRecusa.CLIENTE_BLOQUEADO, mensagem)
        if leilao.carta.vendedor.ehOMesmo(self):
            raise LanceRecusado(
                MotivoRecusa.PROPRIO_LEILAO,
                "Você é o vendedor desta carta e não pode dar lances no próprio leilão.",
            )
        lance = Lance(valor=reais(valor), dataHora=agora or datetime.now(UTC), cliente=self)
        leilao.receberLance(lance)
        return lance
