import pytest

from apoio import CSRF, criar_conta, lance_json, leilao_id


@pytest.fixture
def logado(cliente_http):
    criar_conta(cliente_http)
    return cliente_http


@pytest.mark.parametrize("url", ["/minha-conta", "/minha-conta/carteira", "/minha-conta/lances"])
def test_exige_login(cliente_http, url):
    resposta = cliente_http.get(url)
    assert resposta.status_code == 302
    assert resposta.headers["Location"].startswith("/entrar?proximo=")


def test_perfil_mostra_dados_de_usuario_e_cliente_com_cpf_mascarado(logado):
    pagina = logado.get("/minha-conta").get_data(as_text=True)
    for trecho in ("Ana Souza", "ana@teste.com", "(48) 99123-4567", "***.982.247-**",
                   "Cliente desde", "Ativa, liberada para lances", "Descumprimentos"):
        assert trecho in pagina
    assert "529.982.247-25" not in pagina


def test_abas_internas_e_acao_sair(logado):
    pagina = logado.get("/minha-conta/carteira").get_data(as_text=True)
    assert 'href="/minha-conta/carteira" aria-current="page"' in pagina
    assert ">Perfil</a>" in pagina and ">Meus lances</a>" in pagina
    assert 'action="/sair"' in pagina


def test_carteira_mostra_saldo_zero_e_extrato_vazio(logado):
    pagina = logado.get("/minha-conta/carteira").get_data(as_text=True)
    assert "R$ 0,00" in pagina
    assert "Nenhuma movimentação na sua carteira." in pagina
    assert "<form" not in pagina.split('class="conta-conteudo"')[1]


def test_carteira_lista_as_movimentacoes_gravadas(logado, banco):
    carteira = banco.execute(
        "SELECT c.id FROM carteiras c JOIN usuarios u ON u.id = c.cliente_id WHERE u.email = ?", ("ana@teste.com",)
    ).fetchone()["id"]
    banco.execute("INSERT INTO movimentacoes_carteira (carteira_id, tipo, valor_centavos, data_hora, descricao)"
                  " VALUES (?, 'credito', 4250, '2026-10-01T15:00:00.000+00:00', 'Repasse da venda do Pikachu')",
                  (carteira,))
    pagina = logado.get("/minha-conta/carteira").get_data(as_text=True)
    assert "Repasse da venda do Pikachu" in pagina and "R$ 42,50" in pagina


def test_meus_lances_vazio_e_depois_com_o_lance(logado, banco, app):
    assert "Você ainda não deu nenhum lance." in logado.get("/minha-conta/lances").get_data(as_text=True)

    charizard = leilao_id(banco, "Charizard")
    lance_json(logado, charizard, "2.355,00")
    pagina = logado.get("/minha-conta/lances").get_data(as_text=True)
    assert ">Charizard</a>" in pagina and "Você lidera" in pagina and "Ativo" in pagina

    outro = app.test_client()
    with outro.session_transaction() as sessao:
        sessao["csrf"] = CSRF
    criar_conta(outro, email="bruno@teste.com", cpf="111.444.777-35")
    lance_json(outro, charizard, "2.400,00")
    assert "Superado" in logado.get("/minha-conta/lances").get_data(as_text=True)
