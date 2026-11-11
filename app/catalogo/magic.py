"""Magic: The Gathering pela API do Scryfall (https://scryfall.com/docs/api)."""
import re
from urllib.parse import urlencode

from app.catalogo.base import CartaDoCatalogo, PrecoMedio, especificacoes, preco_medio

API = "https://api.scryfall.com/cards"
_UUID = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
# O Scryfall traz o preço do TCGplayer em dólares e o do Cardmarket em euros; vale primeiro o da carta comum.
_PRECOS = (("usd", "USD", "TCGplayer"), ("usd_foil", "USD", "TCGplayer"), ("usd_etched", "USD", "TCGplayer"),
           ("eur", "EUR", "Cardmarket"), ("eur_foil", "EUR", "Cardmarket"))


class Scryfall:
    jogo = "Magic: The Gathering"

    def __init__(self, transporte):
        self.transporte = transporte

    def buscar(self, nome: str) -> list[CartaDoCatalogo]:
        return self._pesquisar(f'name:"{nome.replace(chr(34), " ")}" game:paper')

    def sugestoes(self) -> list[CartaDoCatalogo]:
        # As coleções principais já lançadas: sem a data viriam as cartas anunciadas, ainda sem preço.
        return self._pesquisar("game:paper (st:expansion or st:core) date<=today")

    def _pesquisar(self, consulta: str) -> list[CartaDoCatalogo]:
        # Uma linha por impressão (unique=prints), da mais recente para a mais antiga.
        parametros = urlencode({"q": consulta, "unique": "prints", "order": "released"})
        resposta = self.transporte.json(f"{API}/search?{parametros}", vazio=(400, 404))
        return [carta for dados in (resposta or {}).get("data", []) if (carta := _carta(dados))]

    def obter(self, id: str) -> CartaDoCatalogo | None:
        if not _UUID.match(id):
            return None
        resposta = self.transporte.json(f"{API}/{id}")
        return _carta(resposta) if resposta else None


def _carta(dados: dict) -> CartaDoCatalogo | None:
    # Carta de duas faces traz imagem e texto em card_faces; a frente é a foto.
    faces = dados.get("card_faces") or [dados]
    imagens = dados.get("image_uris") or faces[0].get("image_uris")
    if not imagens:
        return None
    forca = "/".join(valor for valor in (faces[0].get("power"), faces[0].get("toughness")) if valor)
    return CartaDoCatalogo(
        jogo=Scryfall.jogo,
        id=dados["id"],
        nome=dados["name"],
        codigo=f'{dados["set"].upper()} {dados["collector_number"]}',
        edicoes=(f'{dados["set_name"]} ({dados["collector_number"]})',),
        especificacoes=especificacoes(
            ("Tipo", dados.get("type_line")),
            ("Custo de mana", faces[0].get("mana_cost")),
            ("Poder/Resistência", forca),
            ("Raridade", (dados.get("rarity") or "").capitalize()),
            ("Idioma", dados.get("lang", "en").upper()),
        ),
        texto=" // ".join(face["oracle_text"] for face in faces if face.get("oracle_text")),
        miniatura=imagens["normal"],
        imagem=imagens["large"],
        preco=_preco(dados.get("prices") or {}),
    )


def _preco(precos: dict) -> PrecoMedio | None:
    for chave, moeda, fonte in _PRECOS:
        if preco := preco_medio(precos.get(chave), moeda, fonte):
            return preco
    return None
