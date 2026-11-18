"""Yu-Gi-Oh! pelo YGOPRODeck (https://ygoprodeck.com/api-guide/), que proíbe exibir as imagens direto do site."""
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode

from app.catalogo.base import LIMITE_DE_RESULTADOS, CartaDoCatalogo, Filtro, especificacoes, preco_medio

API = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
_SEM_RESULTADO = (400, 404)
_TIPOS_DE_CARTA = (
    "Normal Monster", "Effect Monster", "Fusion Monster", "Ritual Monster", "Ritual Effect Monster",
    "Synchro Monster", "Synchro Tuner Monster", "XYZ Monster", "Link Monster", "Pendulum Normal Monster",
    "Pendulum Effect Monster", "Pendulum Tuner Effect Monster", "Pendulum Effect Fusion Monster",
    "Synchro Pendulum Effect Monster", "XYZ Pendulum Effect Monster", "Tuner Monster", "Normal Tuner Monster",
    "Flip Effect Monster", "Gemini Monster", "Spirit Monster", "Toon Monster", "Union Effect Monster",
    "Spell Card", "Trap Card")
_ATRIBUTOS = ("DARK", "LIGHT", "EARTH", "WATER", "FIRE", "WIND", "DIVINE")
_TIPOS = (
    "Aqua", "Beast", "Beast-Warrior", "Cyberse", "Dinosaur", "Divine-Beast", "Dragon", "Fairy", "Fiend", "Fish",
    "Illusion", "Insect", "Machine", "Plant", "Psychic", "Pyro", "Reptile", "Rock", "Sea Serpent", "Spellcaster",
    "Thunder", "Warrior", "Winged Beast", "Wyrm", "Zombie",
    # Magias e armadilhas
    "Normal", "Continuous", "Counter", "Equip", "Field", "Quick-Play", "Ritual")
_NIVEIS = tuple(str(nivel) for nivel in range(1, 13))
# Aceitam vários valores separados por vírgula; o nível, só um.
_NA_API = {"categoria": "type", "atributo": "attribute", "tipo": "race"}
_PEDIDOS_JUNTOS = 4


class Ygoprodeck:
    jogo = "Yu-Gi-Oh!"
    filtros = (
        Filtro("categoria", "Tipo de carta", _TIPOS_DE_CARTA, ficha="Tipo de carta"),
        Filtro("atributo", "Atributo", _ATRIBUTOS, ficha="Atributo"),
        Filtro("tipo", "Tipo", _TIPOS, ficha="Tipo"),
        Filtro("nivel", "Nível", _NIVEIS, ficha="Nível"),
    )

    def __init__(self, transporte):
        self.transporte = transporte

    def buscar(self, nome: str, filtros: Mapping[str, Sequence[str]] | None = None) -> list[CartaDoCatalogo]:
        filtros = filtros or {}
        consulta = {parametro: ",".join(filtros[chave]) for chave, parametro in _NA_API.items() if chave in filtros}
        consulta |= {"fname": nome} if nome else {"sort": "new", "format": "tcg"}
        niveis = list(filtros.get("nivel", ()))
        if len(niveis) < 2:
            return self._listar(**consulta, **({"level": niveis[0]} if niveis else {}))
        # Um pedido por nível; intercalar mantém todos os níveis no que cabe na página.
        with ThreadPoolExecutor(_PEDIDOS_JUNTOS) as fila:
            listas = list(fila.map(lambda nivel: self._listar(**consulta, level=nivel), niveis))
        return _intercalar(listas)

    def sugestoes(self) -> list[CartaDoCatalogo]:
        # format=tcg: as cartas que só saíram no Japão não têm edição.
        return self._listar(sort="new", format="tcg")

    def _listar(self, **filtro: str) -> list[CartaDoCatalogo]:
        consulta = urlencode({**filtro, "num": LIMITE_DE_RESULTADOS, "offset": 0})
        resposta = self.transporte.json(f"{API}?{consulta}", vazio=_SEM_RESULTADO)
        return [carta for dados in (resposta or {}).get("data", []) if (carta := _carta(dados))]

    def obter(self, id: str) -> CartaDoCatalogo | None:
        if not id.isdigit():
            return None
        resposta = self.transporte.json(f"{API}?id={id}", vazio=_SEM_RESULTADO)
        return _carta(resposta["data"][0]) if resposta and resposta.get("data") else None


def _intercalar(listas: list[list[CartaDoCatalogo]]) -> list[CartaDoCatalogo]:
    maior = max((len(lista) for lista in listas), default=0)
    return [lista[posicao] for posicao in range(maior) for lista in listas if posicao < len(lista)]


def _carta(dados: dict) -> CartaDoCatalogo | None:
    edicoes = tuple(dict.fromkeys(
        f'{colecao["set_name"]} ({colecao["set_code"]})' for colecao in dados.get("card_sets") or []))
    imagens = (dados.get("card_images") or [{}])[0]
    if not edicoes or not imagens.get("image_url"):
        return None
    ataque, defesa = dados.get("atk"), dados.get("def")
    # O preço não distingue a edição.
    precos = (dados.get("card_prices") or [{}])[0]
    return CartaDoCatalogo(
        jogo=Ygoprodeck.jogo,
        id=str(dados["id"]),
        nome=dados["name"],
        codigo=str(dados["id"]).zfill(8),
        edicoes=edicoes,
        especificacoes=especificacoes(
            ("Tipo de carta", dados.get("type")),
            ("Tipo", dados.get("race")),
            ("Atributo", dados.get("attribute")),
            ("Nível", dados.get("level")),
            ("ATK/DEF", f"{ataque}/{defesa}" if ataque is not None and defesa is not None else ataque),
            ("Arquétipo", dados.get("archetype")),
        ),
        texto=dados.get("desc") or "",
        miniatura=imagens.get("image_url_small") or imagens["image_url"],
        imagem=imagens["image_url"],
        preco=(preco_medio(precos.get("tcgplayer_price"), "USD", "TCGplayer")
               or preco_medio(precos.get("cardmarket_price"), "EUR", "Cardmarket")),
    )
