import re

from apoio import CSRF, SENHA, criar_conta, entrar, sair


def test_criar_conta_entra_logado_e_volta_para_a_pagina_de_origem(cliente_http):
    resposta = criar_conta(cliente_http, proximo="/leiloes/3")
    assert resposta.status_code == 303
    assert resposta.headers["Location"] == "/leiloes/3"
    pagina = cliente_http.get("/leiloes/3").get_data(as_text=True)
    assert "Minha Conta" in pagina
    assert "Conta criada" in pagina


def test_criar_conta_com_erros_mostra_cada_erro_no_seu_campo_e_mantem_os_dados(cliente_http):
    resposta = criar_conta(cliente_http, cpf="529.982.247-24", confirmacao="outra-senha")
    assert resposta.status_code == 422
    pagina = resposta.get_data(as_text=True)
    assert 'id="erro-cpf"' in pagina and 'id="erro-confirmacao"' in pagina
    assert re.search(r'id="cpf"[^>]*aria-invalid="true"', pagina, re.S)
    assert 'value="ana@teste.com"' in pagina
    assert SENHA not in pagina


def test_e_mail_repetido_na_tela_de_cadastro(cliente_http, app):
    criar_conta(cliente_http)
    outro = app.test_client()
    with outro.session_transaction() as sessao:
        sessao["csrf"] = CSRF
    resposta = criar_conta(outro, cpf="111.444.777-35")
    assert resposta.status_code == 422
    assert "Este e-mail já tem uma conta" in resposta.get_data(as_text=True)


def test_entrar_com_email_e_senha(cliente_http, app):
    criar_conta(cliente_http)
    cliente_http.post("/sair", data={"csrf_token": CSRF})

    novo = app.test_client()
    with novo.session_transaction() as sessao:
        sessao["csrf"] = CSRF
    resposta = entrar(novo, email="ANA@teste.com")
    assert resposta.status_code == 303
    assert novo.get("/minha-conta").status_code == 200


def test_sessao_sobrevive_ao_recarregamento(cliente_http):
    criar_conta(cliente_http)
    for _ in range(3):
        assert "Minha Conta" in cliente_http.get("/leiloes").get_data(as_text=True)
    with cliente_http.session_transaction() as sessao:
        assert sessao.get("usuario_id") is not None


def test_senha_errada_nao_entra_e_nao_diz_qual_campo_errou(cliente_http, app):
    criar_conta(cliente_http)
    sair(cliente_http)
    errada = entrar(cliente_http, senha="senha-errada")
    inexistente = entrar(cliente_http, email="ninguem@teste.com")
    for resposta in (errada, inexistente):
        assert resposta.status_code == 401
        assert "E-mail ou senha incorretos." in resposta.get_data(as_text=True)
    assert cliente_http.get("/minha-conta").status_code == 302


def test_sair_encerra_a_sessao(cliente_http):
    criar_conta(cliente_http)
    resposta = cliente_http.post("/sair", data={"csrf_token": CSRF})
    assert resposta.status_code == 303
    assert cliente_http.get("/minha-conta").headers["Location"] == "/entrar?proximo=/minha-conta"


def test_sair_exige_post_com_token(cliente_http):
    criar_conta(cliente_http)
    assert cliente_http.get("/sair").status_code == 405
    assert cliente_http.post("/sair", data={}).status_code == 400
    assert cliente_http.get("/minha-conta").status_code == 200


def test_login_nao_redireciona_para_outro_site(cliente_http):
    criar_conta(cliente_http)
    sair(cliente_http)
    for destino in ("https://exemplo.com/roubo", "//exemplo.com", "javascript:alert(1)"):
        resposta = entrar(cliente_http, proximo=destino)
        assert resposta.headers["Location"] == "/leiloes"
        sair(cliente_http)


def test_menu_mostra_entrar_e_criar_conta_para_visitante_e_minha_conta_para_cliente(cliente_http):
    visitante = cliente_http.get("/leiloes").get_data(as_text=True)
    assert ">Entrar</a>" in visitante and ">Criar conta</a>" in visitante
    assert "Minha Conta" not in visitante
    criar_conta(cliente_http)
    logado = cliente_http.get("/leiloes").get_data(as_text=True)
    assert "Minha Conta" in logado and ">Entrar</a>" not in logado


def test_cookie_antigo_com_o_mesmo_id_nao_vale_para_outra_conta(cliente_http, banco):
    outro_id = banco.execute("SELECT MIN(id) FROM usuarios").fetchone()[0]
    with cliente_http.session_transaction() as sessao:
        sessao["usuario_id"] = outro_id
    assert "Minha Conta" not in cliente_http.get("/leiloes").get_data(as_text=True)
    assert cliente_http.get("/minha-conta").status_code == 302
