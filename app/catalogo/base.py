import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from threading import Lock

LIMITE_DE_RESULTADOS = 60
SEIS_HORAS = 6 * 60 * 60


class CatalogoIndisponivel(Exception):
    """A API do jogo não respondeu, ou respondeu algo que não dá para ler."""


@dataclass(frozen=True)
class PrecoMedio:
    """Por quanto a carta é vendida, em média, no mercado que a API consulta, na moeda desse mercado."""
    valor: Decimal
    moeda: str
    fonte: str


@dataclass(frozen=True)
class CartaDoCatalogo:
    jogo: str
    id: str
    nome: str
    codigo: str
    # Mais de uma edição quando a API não separa as impressões da carta (Yu-Gi-Oh!): o vendedor escolhe.
    edicoes: tuple[str, ...]
    especificacoes: tuple[tuple[str, str], ...]
    texto: str
    miniatura: str
    imagem: str
    # None quando a API não tem o preço da carta, ou só informa na ficha dela (Pokémon).
    preco: PrecoMedio | None = None


def especificacoes(*pares: tuple[str, object]) -> tuple[tuple[str, str], ...]:
    """Só as especificações que a API informou, na ordem dada."""
    return tuple((rotulo, str(valor)) for rotulo, valor in pares if valor not in (None, "", []))


def preco_medio(valor: object, moeda: str, fonte: str) -> PrecoMedio | None:
    """O preço que a API informou; None quando ela manda nulo, vazio ou zero, que é como dizem "sem preço"."""
    try:
        valor = Decimal(str(valor))
    except InvalidOperation:
        return None
    return PrecoMedio(valor, moeda, fonte) if valor.is_finite() and valor > 0 else None


class Memoria:
    """Guarda por um tempo o que muda pouco no catálogo (coleções, sugestões), para não repetir a consulta."""

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
        # Resposta vazia não é guardada: a próxima consulta tenta de novo.
        if valor:
            with self._trava:
                self._itens[chave] = (self._relogio() + self._validade, valor)
        return valor
