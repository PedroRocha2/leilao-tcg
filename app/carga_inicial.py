import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal

from app.dominio.contas import Administrador, Cliente
from app.dominio.cpf import completar_cpf
from app.dominio.leiloes import INCREMENTO_DA_LOJA, Carta, Jogo, Leilao, StatusCarta, StatusLeilao
from app.dominio.loja import ConfiguracaoLoja
from app.dominio.senhas import gerar_hash, senha_inutilizavel
from app.repositorios.clientes import RepositorioClientes
from app.repositorios.leiloes import RepositorioLeiloes
from app.repositorios.loja import RepositorioLoja

h = timedelta(hours=1)
m = timedelta(minutes=1)
d = timedelta(days=1)

CLIENTES = [
    ("Rafaela Moura", "rafaela.moura@correio.invalid", "48991230457", "318402956", 220),
    ("Thiago Bastos", "thiago.bastos@correio.invalid", "48998107733", "207615384", 180),
    ("Juliana Okabe", "juliana.okabe@correio.invalid", "48996542108", "460938127", 150),
    ("Marcos Teixeira", "marcos.teixeira@correio.invalid", "48988765412", "571204639", 133),
    ("Patrícia Lemos", "patricia.lemos@correio.invalid", "48999014526", "632810475", 97),
    ("André Kowalski", "andre.kowalski@correio.invalid", "48991876230", "749126308", 64),
    ("Beatriz Nogueira", "beatriz.nogueira@correio.invalid", "48984412975", "805317462", 41),
    ("Caio Fernandes", "caio.fernandes@correio.invalid", "48997320861", "913540286", 18),
]

POKEMON, MAGIC, YUGIOH = "Pokémon", "Magic: The Gathering", "Yu-Gi-Oh!"

CARTAS = [
    (POKEMON, "Charizard", "Base Set (4/102)", "Lightly Played (LP)",
     "Charizard holográfico do Base Set, carta 4 de 102. O holo não tem riscos aparentes e a "
     "centralização é boa; as bordas têm desgaste leve, por isso a classificação Lightly Played. "
     "A loja conferiu a carta na entrega e a guarda em sleeve e toploader até a retirada.",
     "charizard", 0, "1500.00", -3 * d, 5 * h + 50 * m,
     [(1, "1500.00", -40 * h), (2, "1800.00", -22 * h), (3, "2100.00", -5 * h), (1, "2350.00", -1 * h)]),
    (POKEMON, "Blastoise", "Base Set (2/102)", "Near Mint (NM)",
     "Blastoise holográfico do Base Set guardado desde 1999 em fichário de folhas sem PVC. "
     "Cantos firmes, sem marcas de manuseio na frente e brilho intacto no holo.",
     "blastoise", 6, "450.00", -2 * d, 2 * d + 6 * h,
     [(4, "450.00", -30 * h), (2, "520.00", -20 * h), (5, "600.00", -9 * h), (4, "640.00", -2 * h)]),
    (POKEMON, "Venusaur", "Base Set (15/102)", "Moderately Played (MP)",
     "Venusaur holográfico do Base Set com marcas de uso: riscos finos no holo e bordas "
     "esbranquiçadas no verso. Sem dobras nem amassados.",
     "venusaur", 5, "300.00", -1 * d, 19 * h + 12 * m,
     [(3, "300.00", -18 * h), (7, "360.00", -6 * h), (3, "410.00", -40 * m)]),
    (POKEMON, "Pikachu", "Base Set (58/102)", "Near Mint (NM)",
     "Pikachu comum do Base Set, com as bochechas vermelhas da primeira tiragem. "
     "Frente limpa e centralização levemente deslocada para a esquerda.",
     "pikachu", 4, "80.00", -26 * h, 1 * d + 23 * h,
     [(2, "80.00", -20 * h), (1, "90.00", -9 * h), (2, "100.00", -3 * h)]),
    (POKEMON, "Mewtwo", "Base Set (10/102)", "Lightly Played (LP)",
     "Mewtwo holográfico do Base Set. Um ponto branco no canto superior direito do verso; a frente "
     "está sem marcas.",
     "mewtwo", 7, "180.00", -5 * h, 3 * d + 2 * h, []),
    (MAGIC, "Lightning Bolt", "Magic 2010 (146)", "Near Mint (NM)",
     "Lightning Bolt da coleção básica Magic 2010, em inglês. Saiu direto do booster para o sleeve.",
     "lightning-bolt", 0, "20.00", -2 * h, 1 * d, []),
    (MAGIC, "Sol Ring", "Commander 2021 (263)", "Near Mint (NM)",
     "Sol Ring do deck pré-construído Commander 2021, em inglês. Nunca foi jogado sem sleeve.",
     "sol-ring", 3, "45.00", -30 * h, 3 * d,
     [(1, "45.00", -12 * h), (5, "52.00", -2 * h)]),
    (MAGIC, "Shivan Dragon", "Magic 2010 (156)", "Lightly Played (LP)",
     "Shivan Dragon da Magic 2010, em inglês. Leve desgaste nas bordas do verso, frente sem riscos.",
     "shivan-dragon", 1, "35.00", -20 * h, 11 * h,
     [(4, "35.00", -15 * h), (6, "40.00", -10 * h), (2, "48.00", -1 * h)]),
    (MAGIC, "Llanowar Elves", "Dominaria (168)", "Near Mint (NM)",
     "Llanowar Elves de Dominaria, em inglês, guardado em toploader desde a abertura do booster.",
     "llanowar-elves", 2, "12.00", -10 * h, 2 * d + 14 * h,
     [(7, "12.00", -4 * h)]),
    (MAGIC, "Counterspell", "Seventh Edition (67)", "Moderately Played (MP)",
     "Counterspell da Seventh Edition, em inglês. Cantos arredondados pelo uso e um risco curto na "
     "arte; carta plana e sem dobras.",
     "counterspell", 4, "25.00", -3 * d, 45 * m,
     [(5, "25.00", -50 * h), (3, "30.00", -30 * h), (5, "38.00", -8 * h), (1, "45.00", -1 * h)]),
    (YUGIOH, "Dark Magician", "Legend of Blue Eyes White Dragon (LOB-005)", "Moderately Played (MP)",
     "Dark Magician ultra rara da coleção Legend of Blue Eyes White Dragon. O foil do nome tem "
     "riscos leves e o verso mostra desgaste nas bordas.",
     "dark-magician", 5, "120.00", -70 * h, 25 * m,
     [(3, "120.00", -50 * h), (1, "140.00", -10 * h), (2, "155.00", -30 * m)]),
    (YUGIOH, "Blue-Eyes White Dragon", "Legend of Blue Eyes White Dragon (LOB-001)", "Lightly Played (LP)",
     "Blue-Eyes White Dragon ultra rara, a carta 001 da primeira coleção em inglês. Foil sem "
     "manchas; um canto do verso com desgaste leve.",
     "blue-eyes-white-dragon", 1, "600.00", -1 * d, 4 * d,
     [(6, "600.00", -20 * h), (7, "650.00", -6 * h)]),
    (YUGIOH, "Red-Eyes Black Dragon", "Legend of Blue Eyes White Dragon (LOB-070)", "Near Mint (NM)",
     "Red-Eyes Black Dragon ultra rara da Legend of Blue Eyes White Dragon. Guardada em sleeve "
     "duplo desde a compra.",
     "red-eyes-black-dragon", 2, "250.00", -2 * d, 2 * d,
     [(4, "250.00", -36 * h), (0, "275.00", -8 * h)]),
    (YUGIOH, "Exodia the Forbidden One", "Legend of Blue Eyes White Dragon (LOB-124)", "Lightly Played (LP)",
     "Exodia the Forbidden One ultra rara, a cabeça do conjunto de cinco peças. Foil íntegro e "
     "bordas com desgaste leve.",
     "exodia", 6, "350.00", -6 * h, 1 * d + 12 * h, []),
    (YUGIOH, "Kuriboh", "Metal Raiders (MRD-071)", "Near Mint (NM)",
     "Kuriboh comum da coleção Metal Raiders, em inglês. Carta limpa, sem marcas na frente nem no verso.",
     "kuriboh", 7, "15.00", -1 * d, 8 * h,
     [(0, "15.00", -20 * h), (4, "20.00", -3 * h)]),
]

FOTOS = ("frente", "arte", "canto")

# Chaves e valores dos filtros de cada jogo (app/catalogo).
ATRIBUTOS = {
    "Charizard": {"categoria": "Pokémon", "tipo": "Fire", "estagio": "Stage2", "raridade": "Rare"},
    "Blastoise": {"categoria": "Pokémon", "tipo": "Water", "estagio": "Stage2", "raridade": "Rare"},
    "Venusaur": {"categoria": "Pokémon", "tipo": "Grass", "estagio": "Stage2", "raridade": "Rare"},
    "Pikachu": {"categoria": "Pokémon", "tipo": "Lightning", "estagio": "Basic", "raridade": "Common"},
    "Mewtwo": {"categoria": "Pokémon", "tipo": "Psychic", "estagio": "Basic", "raridade": "Rare"},
    "Lightning Bolt": {"cor": "Vermelha", "tipo": "Instant", "raridade": "Common"},
    "Sol Ring": {"cor": "Incolor", "tipo": "Artifact", "raridade": "Uncommon"},
    "Shivan Dragon": {"cor": "Vermelha", "tipo": "Creature", "raridade": "Rare"},
    "Llanowar Elves": {"cor": "Verde", "tipo": "Creature", "raridade": "Common"},
    "Counterspell": {"cor": "Azul", "tipo": "Instant", "raridade": "Uncommon"},
    "Dark Magician": {"categoria": "Normal Monster", "atributo": "DARK", "tipo": "Spellcaster", "nivel": "7"},
    "Blue-Eyes White Dragon": {"categoria": "Normal Monster", "atributo": "LIGHT", "tipo": "Dragon", "nivel": "8"},
    "Red-Eyes Black Dragon": {"categoria": "Normal Monster", "atributo": "DARK", "tipo": "Dragon", "nivel": "7"},
    "Exodia the Forbidden One": {"categoria": "Effect Monster", "atributo": "DARK", "tipo": "Spellcaster",
                                 "nivel": "3"},
    "Kuriboh": {"categoria": "Effect Monster", "atributo": "DARK", "tipo": "Fiend", "nivel": "1"},
}


def popular(conexao: sqlite3.Connection, agora: datetime, administrador: dict | None = None) -> None:
    clientes_repo = RepositorioClientes(conexao)
    leiloes_repo = RepositorioLeiloes(conexao, clientes_repo)
    RepositorioLoja(conexao).salvar_configuracao(ConfiguracaoLoja())
    if administrador:
        # O login do lojista fica na coluna do e-mail.
        clientes_repo.adicionar_administrador(Administrador(
            nome="Administrador da loja", email=administrador["login"].strip().lower(), telefone="",
            senhaHash=gerar_hash(administrador["senha"], administrador["iteracoes"]),
            dataCadastro=agora.date()))

    clientes = [
        clientes_repo.adicionar(Cliente(
            nome=nome, email=email, senhaHash=senha_inutilizavel(), telefone=telefone,
            dataCadastro=(agora - dias * d).date(), cpf=completar_cpf(base_cpf),
        ))
        for nome, email, telefone, base_cpf, dias in CLIENTES
    ]
    jogos = {nome: leiloes_repo.adicionar_jogo(Jogo(nome)) for nome in (POKEMON, MAGIC, YUGIOH)}

    for (jogo, nome, edicao, condicao, descricao, arquivo, vendedor, inicial,
         inicio, fim, lances) in CARTAS:
        carta = Carta(nome=nome, jogo=jogos[jogo], edicao=edicao, condicao=condicao,
                      descricao=descricao, vendedor=clientes[vendedor], status=StatusCarta.EM_LEILAO,
                      atributos=list(ATRIBUTOS[nome].items()))
        for foto in FOTOS:
            carta.adicionarFoto(f"img/cartas/{arquivo}-{foto}.webp")
        leilao = Leilao(carta=carta, lanceInicial=Decimal(inicial), incrementoMinimo=INCREMENTO_DA_LOJA,
                        dataInicio=agora + inicio, dataFimPrevista=agora + fim, status=StatusLeilao.ATIVO)
        for cliente, valor, quando in lances:
            clientes[cliente].darLance(leilao, Decimal(valor), agora + quando)
        leiloes_repo.adicionar(leilao)
