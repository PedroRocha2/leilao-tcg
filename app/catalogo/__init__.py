"""Catálogo de cartas: nome, código, edição, especificações, imagem e preço, vindos da API pública de cada jogo."""
from collections import OrderedDict
from dataclasses import replace
from threading import Lock

from app.catalogo.base import (LIMITE_DE_RESULTADOS, CartaDoCatalogo, CatalogoIndisponivel, Memoria,
                               PrecoMedio)
from app.catalogo.http import EXTENSOES, Transporte
from app.catalogo.magic import Scryfall
from app.catalogo.one_piece import Optcg
from app.catalogo.pokemon import Tcgdex
from app.catalogo.yugioh import Ygoprodeck

__all__ = ["EXTENSOES", "CartaDoCatalogo", "Catalogo", "CatalogoIndisponivel", "PrecoMedio", "criar_catalogo"]

_CARTAS_LEMBRADAS = 2000


class Catalogo:
    def __init__(self, transporte, fontes):
        self.transporte = transporte
        self._fontes = {fonte.jogo: fonte for fonte in fontes}
        # As cartas já vistas ficam na memória: escolher uma carta da busca não consulta a API de novo.
        self._cartas: OrderedDict[tuple[str, str], CartaDoCatalogo] = OrderedDict()
        self._sugestoes = Memoria()
        self._trava = Lock()

    @property
    def jogos(self) -> list[str]:
        return list(self._fontes)

    def exemplo_de_codigo(self, jogo: str) -> str | None:
        """Um código de carta, nos jogos em que a busca também acha pelo código impresso na carta."""
        return getattr(self._fontes[jogo], "exemplo_de_codigo", None)

    def buscar(self, jogo: str, texto: str) -> list[CartaDoCatalogo]:
        """As cartas do jogo com `texto` no nome, ou no código quando o catálogo do jogo busca por ele."""
        return self._guardar(self._consultar(self._fontes[jogo].buscar, texto))

    def sugestoes(self, jogo: str) -> list[CartaDoCatalogo]:
        """As cartas mostradas antes de o vendedor filtrar: os lançamentos mais recentes do jogo."""
        fonte = self._fontes[jogo]
        return self._sugestoes.obter(jogo, lambda: self._guardar(self._consultar(fonte.sugestoes)))

    def obter(self, jogo: str, id: str) -> CartaDoCatalogo | None:
        with self._trava:
            carta = self._cartas.get((jogo, id))
        if carta is None and jogo in self._fontes:
            carta = self._consultar(self._fontes[jogo].obter, id)
            if carta is not None:
                self._lembrar(carta)
        return carta

    def preco(self, carta: CartaDoCatalogo) -> PrecoMedio | None:
        """O valor médio de mercado da carta, ou None quando o catálogo do jogo não informa."""
        fonte = self._fontes.get(carta.jogo)
        if carta.preco is not None or not hasattr(fonte, "preco"):
            return carta.preco
        # O TCGdex só informa o preço na ficha da carta: a consulta é feita quando o vendedor escolhe a carta.
        preco = self._consultar(fonte.preco, carta.id)
        if preco is not None:
            self._lembrar(replace(carta, preco=preco))
        return preco

    def imagem(self, url: str) -> tuple[bytes, str]:
        return self.transporte.imagem(url)

    def _consultar(self, consulta, *argumentos):
        try:
            return consulta(*argumentos)
        except (KeyError, TypeError, AttributeError, IndexError) as erro:
            raise CatalogoIndisponivel("A API respondeu em um formato inesperado.") from erro

    def _guardar(self, cartas: list[CartaDoCatalogo]) -> list[CartaDoCatalogo]:
        cartas = cartas[:LIMITE_DE_RESULTADOS]
        for carta in cartas:
            self._lembrar(carta)
        return cartas

    def _lembrar(self, carta: CartaDoCatalogo) -> None:
        with self._trava:
            self._cartas[(carta.jogo, carta.id)] = carta
            self._cartas.move_to_end((carta.jogo, carta.id))
            while len(self._cartas) > _CARTAS_LEMBRADAS:
                self._cartas.popitem(last=False)


def criar_catalogo(user_agent: str, transporte=None) -> Catalogo:
    transporte = transporte or Transporte(user_agent)
    return Catalogo(transporte, [fonte(transporte) for fonte in (Tcgdex, Scryfall, Ygoprodeck, Optcg)])
