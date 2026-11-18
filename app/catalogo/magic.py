"""Magic: The Gathering pela API do Scryfall (https://scryfall.com/docs/api)."""
import re
from collections.abc import Mapping, Sequence
from urllib.parse import urlencode

from app.catalogo.base import CartaDoCatalogo, Filtro, PrecoMedio, especificacoes, por_virgula, preco_medio

API = "https://api.scryfall.com/cards"
_UUID = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
# Em ordem de preferência: a carta comum antes da foil.
_PRECOS = (("usd", "USD", "TCGplayer"), ("usd_foil", "USD", "TCGplayer"), ("usd_etched", "USD", "TCGplayer"),
           ("eur", "EUR", "Cardmarket"), ("eur_foil", "EUR", "Cardmarket"))


_CORES = {"W": "Branca", "U": "Azul", "B": "Preta", "R": "Vermelha", "G": "Verde"}
_INCOLOR = "Incolor"
_TIPOS = ("Creature", "Instant", "Sorcery", "Artifact", "Enchantment", "Land", "Planeswalker", "Battle")
_RARIDADES = ("Common", "Uncommon", "Rare", "Mythic")
_SIMBOLO_DE_MANA = re.compile(r"[WUBRG]")


def _tipos_principais(linha: str) -> list[str]:
    """"Legendary Artifact Creature — Golem": os tipos vêm antes do travessão, em cada face."""
    return [palavra for face in linha.split("//") for palavra in face.split("—")[0].split()]


class Scryfall:
    jogo = "Magic: The Gathering"
    filtros = (
        Filtro("cor", "Cor", (*_CORES.values(), _INCOLOR), ficha="Cor", separar=por_virgula),
        Filtro("tipo", "Tipo", _TIPOS, ficha="Tipo", separar=_tipos_principais),
        Filtro("raridade", "Raridade", _RARIDADES, ficha="Raridade"),
    )

    def __init__(self, transporte):
        self.transporte = transporte

    def buscar(self, nome: str, filtros: Mapping[str, Sequence[str]] | None = None) -> list[CartaDoCatalogo]:
        filtros = filtros or {}
        # "c:c" é a busca do Scryfall por cartas incolores.
        letras = {cor: letra.lower() for letra, cor in _CORES.items()} | {_INCOLOR: "c"}
        consulta = ["game:paper"]
        if nome:
            consulta.insert(0, f'name:"{nome.replace(chr(34), " ")}"')
        for chave, operador, valor in (("cor", "c", letras.get), ("tipo", "t", str.lower), ("raridade", "r", str.lower)):
            termos = [f"{operador}:{valor(opcao)}" for opcao in filtros.get(chave, ())]
            if termos:
                consulta.append(termos[0] if len(termos) == 1 else f'({" or ".join(termos)})')
        return self._pesquisar(" ".join(consulta))

    @staticmethod
    def completar(ficha: dict[str, str]) -> dict[str, str]:
        """Cartas cadastradas antes da especificação "Cor": a cor sai do custo de mana."""
        if "Cor" in ficha or "Custo de mana" not in ficha:
            return ficha
        cores = [_CORES[letra] for letra in dict.fromkeys(_SIMBOLO_DE_MANA.findall(ficha["Custo de mana"]))]
        return {**ficha, "Cor": ", ".join(cores) or _INCOLOR}

    def sugestoes(self) -> list[CartaDoCatalogo]:
        # Sem a data viriam cartas anunciadas, ainda sem preço.
        return self._pesquisar("game:paper (st:expansion or st:core) date<=today")

    def _pesquisar(self, consulta: str) -> list[CartaDoCatalogo]:
        parametros = urlencode({"q": consulta, "unique": "prints", "order": "released"})
        resposta = self.transporte.json(f"{API}/search?{parametros}", vazio=(400, 404))
        return [carta for dados in (resposta or {}).get("data", []) if (carta := _carta(dados))]

    def obter(self, id: str) -> CartaDoCatalogo | None:
        if not _UUID.match(id):
            return None
        resposta = self.transporte.json(f"{API}/{id}")
        return _carta(resposta) if resposta else None


def _carta(dados: dict) -> CartaDoCatalogo | None:
    # Carta de duas faces: imagem, texto e cores ficam em card_faces.
    faces = dados.get("card_faces") or [dados]
    imagens = dados.get("image_uris") or faces[0].get("image_uris")
    if not imagens:
        return None
    forca = "/".join(valor for valor in (faces[0].get("power"), faces[0].get("toughness")) if valor)
    # Lista vazia é carta incolor; sem a lista, não se sabe.
    cores = dados.get("colors") if dados.get("colors") is not None else faces[0].get("colors")
    cor = None if cores is None else (", ".join(_CORES[letra] for letra in cores if letra in _CORES) or _INCOLOR)
    return CartaDoCatalogo(
        jogo=Scryfall.jogo,
        id=dados["id"],
        nome=dados["name"],
        codigo=f'{dados["set"].upper()} {dados["collector_number"]}',
        edicoes=(f'{dados["set_name"]} ({dados["collector_number"]})',),
        especificacoes=especificacoes(
            ("Tipo", dados.get("type_line")),
            ("Cor", cor),
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
