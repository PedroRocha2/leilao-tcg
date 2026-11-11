from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal

from app.dominio import senhas
from app.dominio.dinheiro import reais
from app.dominio.financeiro import Carteira, OperacaoRecusada, Transacao
from app.dominio.leiloes import (TAXA_DA_LOJA, Carta, Jogo, Lance, LanceRecusado, Leilao, MotivoRecusa,
                                 StatusCarta, StatusLeilao)


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
class Administrador(Usuario):
    """O lojista. RN14: só ele acessa as funções administrativas, e não compra nem vende."""


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

    def podeCriarLeilao(self) -> bool:
        return self.ativo and not self.bloqueado

    def cadastrarCarta(self, nome: str, jogo: Jogo, edicao: str, condicao: str, descricao: str,
                       fotos: list[str]) -> Carta:
        """RN04: a carta só vale para leilão com nome, jogo, edição, condição e fotos."""
        faltando = [rotulo for rotulo, valor in (("nome", nome), ("jogo", jogo), ("edição", edicao),
                                                 ("condição", condicao), ("fotos", fotos)) if not valor]
        if faltando:
            raise ValueError(f"RN04: a carta precisa de {', '.join(faltando)}.")
        return Carta(nome=nome, jogo=jogo, edicao=edicao, condicao=condicao, descricao=descricao,
                     vendedor=self, status=StatusCarta.AGUARDANDO_DEPOSITO, fotos=list(fotos))

    def criarLeilao(self, carta: Carta, lanceInicial: Decimal, dataInicio: datetime, dataFimPrevista: datetime,
                    incrementoMinimo: Decimal, agora: datetime | None = None,
                    taxaPercentual: Decimal = TAXA_DA_LOJA) -> Leilao:
        """O leilão nasce pendente: só entra em andamento depois do depósito e da aprovação (RN12)."""
        if not self.podeCriarLeilao():
            raise ValueError("RN15: uma conta bloqueada não pode criar leilões.")
        if not carta.vendedor.ehOMesmo(self):
            raise ValueError("Só o vendedor da carta pode criar um leilão para ela.")
        if dataFimPrevista <= (agora or datetime.now(UTC)):
            raise ValueError("RN05: o fim previsto do leilão precisa estar no futuro.")
        return Leilao(carta=carta, lanceInicial=reais(lanceInicial), incrementoMinimo=incrementoMinimo,
                      dataInicio=dataInicio, dataFimPrevista=dataFimPrevista, status=StatusLeilao.PENDENTE,
                      taxaPercentual=taxaPercentual)

    def pagarArremate(self, transacao: Transacao, comSaldo: Decimal, noGateway: Decimal, forma: str | None,
                      agora: datetime) -> None:
        """RF11. RN18: o saldo da carteira só é debitado na confirmação do pagamento."""
        if not transacao.comprador.ehOMesmo(self):
            raise OperacaoRecusada("Só quem arrematou a carta pode pagar este arremate.")
        if comSaldo > 0 and not self.carteira.possuiSaldo(comSaldo):
            raise OperacaoRecusada("O saldo disponível na carteira não cobre este valor.")
        transacao.confirmarPagamento(comSaldo, noGateway, forma, agora)
        if comSaldo > 0:
            self.carteira.debitar(comSaldo, "Pagamento de arremate", agora)

    def registrarDescumprimento(self) -> None:
        """RN06: o comprador não pagou o arremate dentro do prazo."""
        self.descumprimentos += 1
