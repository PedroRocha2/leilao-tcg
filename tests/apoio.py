import base64
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from app.apresentacao import FUSO_DA_LOJA
from app.catalogo import Catalogo, CatalogoIndisponivel, criar_catalogo
from app.correio import CorreioIndisponivel
from app.db import agora_utc
from app.dominio import senhas
from app.dominio.contas import Cliente
from app.dominio.cpf import completar_cpf
from app.dominio.leiloes import Carta, Jogo, Leilao, StatusLeilao

ITERACOES_DE_TESTE = 1_000
SENHA = "segredo-forte"
CSRF = "token-de-teste"
ADMIN_LOGIN, ADMIN_SENHA = "admin-jiujitsu", "osscachorro"

AGORA = datetime(2026, 10, 14, 15, 0, tzinfo=UTC)


def novo_cliente(id_: int, base_cpf: str = "111444777", **campos) -> Cliente:
    dados = {
        "id": id_, "nome": f"Cliente {id_}", "email": f"cliente{id_}@teste.com",
        "senhaHash": senhas.gerar_hash(SENHA, ITERACOES_DE_TESTE), "telefone": "48991234567",
        "dataCadastro": date(2026, 1, 10), "cpf": completar_cpf(base_cpf),
    }
    dados.update(campos)
    return Cliente(**dados)


def novo_leilao(vendedor: Cliente, *, lance_inicial="100.00", incremento="5.00",
                inicio=AGORA - timedelta(days=1), fim=AGORA + timedelta(days=1),
                status=StatusLeilao.ATIVO) -> Leilao:
    carta = Carta(nome="Charizard", jogo=Jogo("Pokémon", 1), edicao="Base Set (4/102)",
                  condicao="Lightly Played (LP)", descricao="Holo sem riscos.", vendedor=vendedor,
                  status="em leilão", fotos=["img/cartas/charizard-frente.webp"])
    return Leilao(carta=carta, lanceInicial=Decimal(lance_inicial), incrementoMinimo=Decimal(incremento),
                  dataInicio=inicio, dataFimPrevista=fim, status=status, id=1)


def leilao_id(banco, nome_da_carta: str) -> int:
    return banco.execute(
        "SELECT l.id FROM leiloes l JOIN cartas c ON c.id = l.carta_id WHERE c.nome = ?", (nome_da_carta,)
    ).fetchone()["id"]


AMOSTRAS_DO_CATALOGO = Path(__file__).parent / "dados" / "catalogo"
IMAGEM_DE_TESTE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
ID_DO_RAIO = "bba5ea18-4e58-42a8-b613-2178706476a6"


def amostra(nome: str):
    return json.loads((AMOSTRAS_DO_CATALOGO / f"{nome}.json").read_text(encoding="utf-8"))


class TransporteFalso:
    """Responde como as APIs de cartas, com as amostras gravadas em tests/dados/catalogo, sem usar a rede.

    Buscas pelo nome que acham cartas: "charizard" (Pokémon), "lightning" (Magic), "dark" (Yu-Gi-Oh!) e
    "luffy" (One Piece). Pelo código: "90/112", "4/102" e "004/198" (Pokémon) e "OP02-02…" (One Piece).
    As sugestões de cada jogo e os preços também vêm das amostras.
    """

    def __init__(self):
        self.pedidos: list[str] = []
        self.corpos: list[dict] = []
        self.fora_do_ar = False

    def json(self, url: str, corpo: dict | None = None, vazio: tuple[int, ...] = (404,)):
        self._registrar(url)
        if corpo is not None:
            self.corpos.append(corpo)
        partes = urlsplit(url)
        consulta = {chave: valores[0] for chave, valores in parse_qs(partes.query).items()}
        if partes.hostname == "api.scryfall.com":
            if partes.path == "/cards/search":
                if "date<=today" in consulta["q"]:
                    return amostra("magic_sugestoes")
                return amostra("magic_busca") if "lightning" in consulta["q"].lower() else None
            return amostra("magic_carta") if partes.path.endswith(ID_DO_RAIO) else None
        if partes.hostname == "api.tcgdex.net":
            return self._tcgdex(partes.path, corpo)
        if partes.hostname == "db.ygoprodeck.com":
            if "sort" in consulta:
                return amostra("yugioh_sugestoes")
            if "fname" in consulta:
                return amostra("yugioh_busca") if "dark" in consulta["fname"].lower() else None
            return amostra("yugioh_carta") if consulta["id"] == "46986414" else None
        if partes.hostname == "optcgapi.com":
            return self._optcg(partes.path, consulta)
        raise AssertionError(f"Pedido inesperado ao catálogo: {url}")

    def _tcgdex(self, caminho: str, corpo: dict | None):
        if corpo is None:
            return amostra("pokemon_fichas").get(caminho.rsplit("/", 1)[-1])
        variaveis = corpo["variables"]
        if not variaveis:
            return amostra("pokemon_colecoes")
        if "nome" in variaveis:
            achou = "chariz" in variaveis["nome"].lower()
            return amostra("pokemon_busca") if achou else {"data": {"cards": []}}
        if "numero" in variaveis:
            # Como o TCGdex: o filtro acha o número em qualquer parte ("90" traz 090, 190 e BW90).
            cartas = amostra("pokemon_numero")["data"]["cards"]
            return {"data": {"cards": [carta for carta in cartas if variaveis["numero"] in carta["localId"]]}}
        if "colecao" in variaveis:
            arquivo = f'pokemon_colecao_{variaveis["colecao"].rstrip("-")}'
            existe = (AMOSTRAS_DO_CATALOGO / f"{arquivo}.json").exists()
            return amostra(arquivo) if existe else {"data": {"cards": []}}
        if "id" in variaveis:
            return amostra("pokemon_carta") if variaveis["id"] == "base1-4" else {"data": {"card": None}}
        cartas = amostra("pokemon_cartas")
        return {"data": {nome: cartas.get(id) for nome, id in variaveis.items()}}

    def _optcg(self, caminho: str, consulta: dict[str, str]):
        _, grupo, *resto = caminho.strip("/").split("/")
        if grupo == "allSets":
            return amostra("one_piece_colecoes")
        if resto == ["filtered"] and "card_image_id" in consulta:
            # Como a OPTCG API: o filtro acha o código em qualquer parte, sem diferenciar maiúsculas.
            trecho = consulta["card_image_id"].lower()
            return [carta for carta in amostra("one_piece_codigo")[grupo]
                    if trecho in carta["card_image_id"].lower()] or None
        if resto == ["filtered"]:
            return amostra(f"one_piece_{grupo}") if "luffy" in consulta["card_name"].lower() else None
        if resto[0] == "card":
            return amostra("one_piece_carta") if (grupo, resto[1:]) == ("sets", ["OP01-024"]) else None
        return amostra("one_piece_colecao") if (grupo, resto) == ("sets", ["EB-05"]) else None

    def imagem(self, url: str) -> tuple[bytes, str]:
        self._registrar(url)
        return IMAGEM_DE_TESTE, "image/png"

    def _registrar(self, url: str) -> None:
        self.pedidos.append(url)
        if self.fora_do_ar:
            raise CatalogoIndisponivel("fora do ar (teste)")


def catalogo_de_teste() -> Catalogo:
    return criar_catalogo("teste", TransporteFalso())


class CorreioFalso:
    """Guarda os e-mails que a loja mandaria, como (destinatário, assunto, texto), sem falar com servidor nenhum."""
    externo = True

    def __init__(self):
        self.enviados: list[tuple[str, str, str]] = []
        self.fora_do_ar = False

    def enviar(self, destinatario: str, assunto: str, texto: str) -> None:
        if self.fora_do_ar:
            raise CorreioIndisponivel("fora do ar (teste)")
        self.enviados.append((destinatario, assunto, texto))


def avancar_relogio(app, **quanto) -> None:
    """Faz a aplicação enxergar o relógio adiantado, como se o tempo tivesse passado."""
    app.config["RELOGIO"] = lambda: agora_utc() + timedelta(**quanto)


def criar_conta(navegador, email="ana@teste.com", cpf="529.982.247-25", senha=SENHA, **extras):
    dados = {"csrf_token": CSRF, "nome": "Ana Souza", "email": email, "telefone": "(48) 99123-4567",
             "cpf": cpf, "senha": senha, "confirmacao": senha}
    dados.update(extras)
    resposta = navegador.post("/criar-conta", data=dados)
    with navegador.session_transaction() as sessao:
        sessao["csrf"] = CSRF
    return resposta


def outro_navegador(app, email="bruno@teste.com", cpf="111.444.777-35"):
    """Um segundo cliente, já com conta criada e logado."""
    navegador = app.test_client()
    with navegador.session_transaction() as sessao:
        sessao["csrf"] = CSRF
    criar_conta(navegador, email=email, cpf=cpf)
    return navegador


def no_fuso_da_loja(app, **depois) -> str:
    """O relógio da aplicação, adiantado ou atrasado, no formato do campo de data e hora."""
    return (app.config["RELOGIO"]().astimezone(FUSO_DA_LOJA) + timedelta(**depois)).strftime("%Y-%m-%dT%H:%M")


def criar_leilao(navegador, app, **mudancas):
    """O cliente logado cria o leilão do Charizard do catálogo de teste; `mudancas` troca campos do formulário."""
    dados = {"csrf_token": CSRF, "jogo": "pokemon", "carta": "base1-4", "condicao": "Near Mint (NM)",
             "descricao": "Holo sem riscos e bordas limpas.", "lance_inicial": "50,00",
             "inicio": no_fuso_da_loja(app), "fim": no_fuso_da_loja(app, days=3)}
    dados.update(mudancas)
    return navegador.post("/vender/novo", data=dados)


def leiloes_criados(banco):
    """Os leilões criados depois da carga inicial, com os dados da carta."""
    return banco.execute(
        """SELECT l.*, c.nome, c.edicao, c.condicao, c.descricao, c.status AS status_da_carta, c.vendedor_id,
                  j.nome AS jogo, (SELECT url FROM carta_fotos f WHERE f.carta_id = c.id) AS foto
             FROM leiloes l JOIN cartas c ON c.id = l.carta_id JOIN jogos j ON j.id = c.jogo_id
            WHERE l.id > 15 ORDER BY l.id""").fetchall()


def navegador_admin(app):
    """Um navegador de teste já logado como o lojista."""
    navegador = app.test_client()
    with navegador.session_transaction() as sessao:
        sessao["csrf"] = CSRF
    resposta = entrar(navegador, ADMIN_LOGIN, ADMIN_SENHA)
    assert resposta.status_code == 303, "o administrador não conseguiu entrar"
    return navegador


def aprovar_leilao(app, numero: int) -> str:
    """O lojista aprova o leilão; devolve o texto da página que ele vê em seguida."""
    return navegador_admin(app).post(f"/admin/leiloes/{numero}/aprovar", data={"csrf_token": CSRF},
                                     follow_redirects=True).get_data(as_text=True)


def entrar(navegador, email="ana@teste.com", senha=SENHA, **extras):
    resposta = navegador.post("/entrar", data={"csrf_token": CSRF, "email": email, "senha": senha, **extras})
    with navegador.session_transaction() as sessao:
        sessao["csrf"] = CSRF
    return resposta


def lance_json(navegador, id_do_leilao: int, valor: str):
    return navegador.post(f"/leiloes/{id_do_leilao}/lances", data={"csrf_token": CSRF, "valor": valor},
                          headers={"Accept": "application/json"})


def sair(navegador):
    resposta = navegador.post("/sair", data={"csrf_token": CSRF})
    with navegador.session_transaction() as sessao:
        sessao["csrf"] = CSRF
    return resposta
