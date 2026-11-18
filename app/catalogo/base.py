import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from threading import Lock

LIMITE_DE_RESULTADOS = 60
SEIS_HORAS = 6 * 60 * 60


class CatalogoIndisponivel(Exception):
    """A API do jogo não respondeu ou respondeu algo ilegível."""


@dataclass(frozen=True)
class PrecoMedio:
    valor: Decimal
    moeda: str
    fonte: str


@dataclass(frozen=True)
class CartaDoCatalogo:
    jogo: str
    id: str
    nome: str
    codigo: str
    # Várias quando a API não separa as impressões (Yu-Gi-Oh!): o vendedor escolhe.
    edicoes: tuple[str, ...]
    especificacoes: tuple[tuple[str, str], ...]
    texto: str
    miniatura: str
    imagem: str
    # None também quando o preço só vem na ficha da carta (Pokémon).
    preco: PrecoMedio | None = None


@dataclass(frozen=True)
class Filtro:
    """`ficha` é o rótulo da especificação; `separar` divide valores múltiplos ("Fire, Water")."""
    chave: str
    rotulo: str
    opcoes: tuple[str, ...]
    ficha: str
    separar: Callable[[str], Iterable[str]] | None = None
    nomes: Mapping[str, str] = field(default_factory=dict)

    def nome(self, valor: str) -> str:
        return self.nomes.get(valor, valor)

    def valores(self, especificacoes: Mapping[str, str]) -> list[str]:
        texto = especificacoes.get(self.ficha)
        if not texto:
            return []
        achados = self.separar(texto) if self.separar else [texto]
        return [valor for valor in dict.fromkeys(achados) if valor in self.opcoes]


def atributos(filtros: Iterable[Filtro], especificacoes: Iterable[tuple[str, str]]) -> tuple[tuple[str, str], ...]:
    ficha = dict(especificacoes)
    return tuple((filtro.chave, valor) for filtro in filtros for valor in filtro.valores(ficha))


def por_virgula(texto: str) -> list[str]:
    return [parte.strip() for parte in texto.split(",") if parte.strip()]


def especificacoes(*pares: tuple[str, object]) -> tuple[tuple[str, str], ...]:
    return tuple((rotulo, str(valor)) for rotulo, valor in pares if valor not in (None, "", []))


def preco_medio(valor: object, moeda: str, fonte: str) -> PrecoMedio | None:
    """None quando a API manda nulo, vazio ou zero ("sem preço")."""
    try:
        valor = Decimal(str(valor))
    except InvalidOperation:
        return None
    return PrecoMedio(valor, moeda, fonte) if valor.is_finite() and valor > 0 else None


class Memoria:
    """Cache com validade para consultas que mudam pouco (coleções, sugestões)."""

    def __init__(self, validade: float = SEIS_HORAS, relogio=time.monotonic):
        self._validade = validade
        self._relogio = relogio
        self._itens: dict[object, tuple[float, object]] = {}
        self._trava = Lock()

    def obter(self, chave, consultar):
        with self._trava:
            guardado = self._itens.get(chave)
        if guardado and self._relogio() < guardado[0]:
            return guardado[1]
        valor = consultar()
        # Resposta vazia não fica guardada: a próxima consulta tenta de novo.
        if valor:
            with self._trava:
                self._itens[chave] = (self._relogio() + self._validade, valor)
        return valor
