import re
import threading
from datetime import timedelta

import pytest

from apoio import CSRF, criar_conta, lance_json, leilao_id
from app.db import agora_utc, conectar, para_texto
from app.carga_inicial import CLIENTES


@pytest.fixture
def charizard(banco):
    return leilao_id(banco, "Charizard")


@pytest.fixture
def logado(cliente_http):
    criar_conta(cliente_http)
    return cliente_http


def lances_gravados(banco, id_do_leilao):
    return [linha["valor_centavos"] for linha in banco.execute(
        "SELECT valor_centavos FROM lances WHERE leilao_id = ? ORDER BY id", (id_do_leilao,))]


def test_lista_mostra_os_leiloes_ativos_com_lance_atual_e_tempo(cliente_http):
    pagina = cliente_http.get("/leiloes").get_data(as_text=True)
    assert pagina.count('class="cartao"') == 15
    assert "R$ 2.350,00" in pagina and "Termina em" in pagina
    assert "Lance inicial" in pagina


def test_lista_nao_mostra_leilao_encerrado_nem_fora_do_status_ativo(cliente_http, banco):
    passado = para_texto(agora_utc() - timedelta(minutes=1))
    banco.execute("UPDATE leiloes SET status = 'cancelado' WHERE id = ?", (leilao_id(banco, "Kuriboh"),))
    banco.execute("UPDATE leiloes SET data_fim_prevista = ? WHERE id = ?", (passado, leilao_id(banco, "Mewtwo")))
    pagina = cliente_http.get("/leiloes").get_data(as_text=True)
    assert pagina.count('class="cartao"') == 13
    assert ">Kuriboh<" not in pagina and ">Mewtwo<" not in pagina


def test_chips_filtram_por_jogo(cliente_http):
    pagina = cliente_http.get("/leiloes?jogo=yu-gi-oh").get_data(as_text=True)
    assert pagina.count('class="cartao"') == 5
    assert ">Dark Magician<" in pagina and ">Charizard<" not in pagina
    assert re.search(r'jogo=yu-gi-oh"\s+aria-current="page"', pagina)


def test_jogo_desconhecido_volta_para_todos(cliente_http):
    assert cliente_http.get("/leiloes?jogo=xadrez").headers["Location"] == "/leiloes"


def test_pagina_tem_trilha_dados_da_carta_e_abas(cliente_http, charizard):
    pagina = cliente_http.get(f"/leiloes/{charizard}").get_data(as_text=True)
    assert re.search(r"Leilões</a>.*Pokémon</a>.*Charizard", pagina, re.S)
    assert "Base Set (4/102)" in pagina and "Lightly Played (LP)" in pagina
    assert "Lance inicial R$ 1.500,00" in pagina and "Incremento mínimo R$ 5,00" in pagina
    for titulo in ("Lances", "Detalhes", "Descrição"):
        assert f">{titulo}</h3>" in pagina
    assert "Outros leilões de Pokémon" in pagina
    assert pagina.count('class="miniatura"') == 3


def test_visitante_ve_entrar_para_dar_lance(cliente_http, charizard):
    pagina = cliente_http.get(f"/leiloes/{charizard}").get_data(as_text=True)
    assert "Entrar para dar lance" in pagina
    assert f'href="/entrar?proximo=/leiloes/{charizard}"' in pagina or "proximo=%2Fleiloes" in pagina
    assert "data-form-lance" not in pagina


def test_campo_vem_preenchido_com_o_lance_minimo(logado, charizard):
    pagina = logado.get(f"/leiloes/{charizard}").get_data(as_text=True)
    assert re.search(r'id="valor-lance"[^>]*value="2.355,00"', pagina, re.S)


def test_licitantes_aparecem_anonimizados(logado, charizard):
    pagina = logado.get(f"/leiloes/{charizard}").get_data(as_text=True)
    assert "Licitante 1" in pagina and "Licitante 3" in pagina
    for nome, *_ in CLIENTES:
        assert nome not in pagina
        assert nome.split()[0] not in pagina


def test_maior_lance_destacado_na_tabela(cliente_http, charizard):
    pagina = cliente_http.get(f"/leiloes/{charizard}").get_data(as_text=True)
    linha_maior = re.search(r'<tr class="maior">(.*?)</tr>', pagina, re.S).group(1)
    assert "R$ 2.350,00" in linha_maior and "Maior lance" in linha_maior


def test_leilao_inexistente(cliente_http):
    assert cliente_http.get("/leiloes/9999").status_code == 404


def test_lance_valido_e_gravado_e_o_minimo_recalculado(logado, banco, charizard, app):
    resposta = lance_json(logado, charizard, "2.355,00")
    assert resposta.status_code == 201
    corpo = resposta.get_json()
    assert corpo["ok"] is True
    assert "Você está liderando" in corpo["mensagem"]
    assert corpo["estado"]["minimo_numero"] == "2.360,00"
    assert corpo["estado"]["total_lances"] == 5
    assert "<strong>Você</strong>" in corpo["tabela"]
    assert lances_gravados(banco, charizard)[-1] == 235500

    outro_visitante = app.test_client()
    assert "R$ 2.355,00" in outro_visitante.get(f"/leiloes/{charizard}").get_data(as_text=True)


def test_lance_abaixo_do_minimo_e_recusado_com_o_motivo(logado, banco, charizard):
    antes = lances_gravados(banco, charizard)
    resposta = lance_json(logado, charizard, "2.354,99")
    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo["motivo"] == "abaixo_do_minimo"
    assert "O lance mínimo agora é R$ 2.355,00" in corpo["mensagem"]
    assert lances_gravados(banco, charizard) == antes


def test_primeiro_lance_usa_o_lance_inicial(logado, banco):
    mewtwo = leilao_id(banco, "Mewtwo")
    assert lance_json(logado, mewtwo, "179,99").status_code == 422
    assert lance_json(logado, mewtwo, "180,00").status_code == 201


def test_formulario_sem_javascript_tambem_aplica_as_regras(logado, banco, charizard):
    recusado = logado.post(f"/leiloes/{charizard}/lances", data={"csrf_token": CSRF, "valor": "2.000,00"})
    assert recusado.status_code == 422
    pagina = recusado.get_data(as_text=True)
    assert 'role="alert"' in pagina and "O lance mínimo agora é" in pagina
    assert re.search(r'id="valor-lance"[^>]*value="2.000,00"', pagina, re.S)

    aceito = logado.post(f"/leiloes/{charizard}/lances", data={"csrf_token": CSRF, "valor": "2.400,00"})
    assert aceito.status_code == 303
    assert "registrado" in logado.get(aceito.headers["Location"]).get_data(as_text=True)


def test_valor_mal_formatado(logado, charizard):
    resposta = lance_json(logado, charizard, "dois mil")
    assert resposta.status_code == 422
    assert "formato inválido" in resposta.get_json()["mensagem"]


def test_visitante_nao_da_lance(cliente_http, banco, charizard):
    antes = lances_gravados(banco, charizard)
    resposta = lance_json(cliente_http, charizard, "9.999,00")
    assert resposta.status_code == 401
    assert resposta.get_json()["entrar"].startswith("/entrar")
    assert lances_gravados(banco, charizard) == antes


def test_lance_sem_token_csrf_e_recusado(logado, charizard):
    resposta = logado.post(f"/leiloes/{charizard}/lances", data={"valor": "9.999,00"},
                           headers={"Accept": "application/json"})
    assert resposta.status_code == 400


def test_cliente_bloqueado_nao_da_lance(logado, banco, charizard):
    banco.execute("UPDATE clientes SET bloqueado = 1 WHERE usuario_id = (SELECT id FROM usuarios WHERE email = ?)",
                  ("ana@teste.com",))
    pagina = logado.get(f"/leiloes/{charizard}").get_data(as_text=True)
    assert "Sua conta está bloqueada para lances" in pagina and "data-form-lance" not in pagina
    resposta = lance_json(logado, charizard, "9.999,00")
    assert resposta.status_code == 422 and resposta.get_json()["motivo"] == "cliente_bloqueado"


def test_vendedor_nao_da_lance_no_proprio_leilao(logado, banco, charizard):
    ana = banco.execute("SELECT id FROM usuarios WHERE email = ?", ("ana@teste.com",)).fetchone()["id"]
    banco.execute("UPDATE cartas SET vendedor_id = ? WHERE id = (SELECT carta_id FROM leiloes WHERE id = ?)",
                  (ana, charizard))
    assert "Você é o vendedor desta carta" in logado.get(f"/leiloes/{charizard}").get_data(as_text=True)
    resposta = lance_json(logado, charizard, "9.999,00")
    assert resposta.status_code == 422 and resposta.get_json()["motivo"] == "proprio_leilao"


def test_leilao_fora_do_prazo_nao_recebe_lance(logado, banco, charizard):
    banco.execute("UPDATE leiloes SET data_fim_prevista = ? WHERE id = ?",
                  (para_texto(agora_utc() - timedelta(seconds=1)), charizard))
    pagina = logado.get(f"/leiloes/{charizard}").get_data(as_text=True)
    assert "Encerrado" in pagina and "Este leilão não recebe mais lances" in pagina
    resposta = lance_json(logado, charizard, "9.999,00")
    assert resposta.status_code == 422 and resposta.get_json()["motivo"] == "prazo_encerrado"


def test_leilao_que_nao_esta_ativo_nao_recebe_lance(logado, banco, charizard):
    banco.execute("UPDATE leiloes SET status = 'encerrado' WHERE id = ?", (charizard,))
    resposta = lance_json(logado, charizard, "9.999,00")
    assert resposta.status_code == 422 and resposta.get_json()["motivo"] == "leilao_inativo"


def test_rn02_lance_nos_ultimos_3_minutos_prorroga_o_fim(logado, banco, charizard):
    fim = agora_utc() + timedelta(minutes=2)
    banco.execute("UPDATE leiloes SET data_fim_prevista = ? WHERE id = ?", (para_texto(fim), charizard))
    resposta = lance_json(logado, charizard, "2.355,00")
    assert resposta.status_code == 201
    gravado = banco.execute("SELECT data_fim_prevista FROM leiloes WHERE id = ?", (charizard,)).fetchone()[0]
    assert gravado == para_texto(fim + timedelta(minutes=3))
    assert resposta.get_json()["estado"]["fim_iso"] == gravado


def test_rn03_banco_recusa_alterar_ou_apagar_lance(banco, charizard):
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError, match="RN03"):
        banco.execute("UPDATE lances SET valor_centavos = 1 WHERE leilao_id = ?", (charizard,))
    with pytest.raises(sqlite3.IntegrityError, match="RN03"):
        banco.execute("DELETE FROM lances WHERE leilao_id = ?", (charizard,))


def test_rn13_dois_lances_simultaneos_de_mesmo_valor_so_um_e_aceito(app, banco, charizard):
    clientes = []
    for numero, cpf in enumerate(["529.982.247-25", "111.444.777-35"]):
        navegador = app.test_client()
        with navegador.session_transaction() as sessao:
            sessao["csrf"] = CSRF
        criar_conta(navegador, email=f"pessoa{numero}@teste.com", cpf=cpf)
        clientes.append(navegador)

    largada = threading.Barrier(2)
    respostas = []

    def disputar(navegador):
        largada.wait()
        respostas.append(lance_json(navegador, charizard, "2.400,00").status_code)

    threads = [threading.Thread(target=disputar, args=(c,)) for c in clientes]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(respostas) == [201, 422]
    assert lances_gravados(banco, charizard).count(240000) == 1


def test_estado_json_traz_o_painel_e_a_tabela(cliente_http, charizard):
    corpo = cliente_http.get(f"/leiloes/{charizard}/estado").get_json()
    assert corpo["estado"]["valor_centavos"] == 235000
    assert corpo["estado"]["minimo_centavos"] == 235500
    assert corpo["estado"]["aberto"] is True
    assert "Maior lance" in corpo["tabela"]


def test_nenhuma_tela_fala_em_demonstracao(cliente_http, charizard):
    for url in ("/leiloes", f"/leiloes/{charizard}", "/entrar", "/criar-conta"):
        pagina = cliente_http.get(url).get_data(as_text=True).lower()
        assert "demo" not in pagina and "em breve" not in pagina
