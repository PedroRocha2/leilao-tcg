"""Construtores e atalhos usados pelos testes (domínio em memória e chamadas HTTP)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.dominio import senhas
from app.dominio.contas import Cliente
from app.dominio.cpf import completar_cpf
from app.dominio.leiloes import Carta, Jogo, Leilao, StatusLeilao

ITERACOES_DE_TESTE = 1_000  # PBKDF2 rápido nos testes; o app usa 600 mil
SENHA = "segredo-forte"
CSRF = "token-de-teste"


# ---------- Domínio (sem banco) ----------

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


# ---------- Atalhos HTTP ----------

def leilao_id(banco, nome_da_carta: str) -> int:
    return banco.execute(
        "SELECT l.id FROM leiloes l JOIN cartas c ON c.id = l.carta_id WHERE c.nome = ?", (nome_da_carta,)
    ).fetchone()["id"]


def criar_conta(navegador, email="ana@teste.com", cpf="529.982.247-25", senha=SENHA, **extras):
    dados = {"csrf_token": CSRF, "nome": "Ana Souza", "email": email, "telefone": "(48) 99123-4567",
             "cpf": cpf, "senha": senha, "confirmacao": senha}
    dados.update(extras)
    resposta = navegador.post("/criar-conta", data=dados)
    with navegador.session_transaction() as sessao:
        sessao["csrf"] = CSRF  # o login gera uma sessão nova; o teste volta a fixar o token
    return resposta


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
