"""As fotos que o vendedor tira da própria carta ao criar o leilão (RF03, RN04)."""
import io
from pathlib import Path

import pytest

from apoio import CSRF, IMAGEM_DE_TESTE, aprovar_leilao, criar_conta, criar_leilao, leiloes_criados, navegador_admin
from app.anuncio import MAXIMO_DE_FOTOS, TAMANHO_MAXIMO_DA_FOTO, foto_do_vendedor, tipo_da_imagem

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 32


@pytest.fixture
def logado(cliente_http):
    criar_conta(cliente_http)
    return cliente_http


def anexos(*conteudos):
    return [(io.BytesIO(dados), f"foto-{numero}.jpg") for numero, dados in enumerate(conteudos, start=1)]


def fotos_da_carta(banco, numero):
    return [linha["url"] for linha in banco.execute(
        "SELECT f.url FROM carta_fotos f JOIN leiloes l ON l.carta_id = f.carta_id WHERE l.id = ? ORDER BY f.ordem",
        (numero,))]


def arquivos(app):
    pasta = Path(app.config["PASTA_DE_FOTOS"])
    return sorted(pasta.iterdir()) if pasta.exists() else []


@pytest.mark.parametrize("dados, tipo", [
    (JPEG, "image/jpeg"), (IMAGEM_DE_TESTE, "image/png"), (WEBP, "image/webp"),
    (b"GIF89a" + b"\x00" * 20, None), (b"<svg xmlns='http://www.w3.org/2000/svg'/>", None), (b"", None),
])
def test_formato_da_foto_e_reconhecido_pelo_conteudo(dados, tipo):
    assert tipo_da_imagem(dados) == tipo


def test_formulario_tem_o_campo_de_fotos_opcional(logado):
    pagina = logado.get("/vender/novo?jogo=pokemon&carta=base1-4").get_data(as_text=True)
    assert 'enctype="multipart/form-data"' in pagina
    assert 'name="fotos" type="file" accept="image/jpeg,image/png,image/webp" multiple' in pagina
    assert f"Até {MAXIMO_DE_FOTOS} fotos" in pagina and "(opcional)" in pagina


def test_fotos_do_vendedor_sao_gravadas_depois_da_imagem_do_catalogo(logado, app, banco):
    resposta = criar_leilao(logado, app, fotos=anexos(JPEG, WEBP))
    assert resposta.status_code == 303

    numero = leiloes_criados(banco)[0]["id"]
    catalogo, primeira, segunda = fotos_da_carta(banco, numero)
    assert catalogo.endswith("-catalogo.png") and not foto_do_vendedor(catalogo)
    assert primeira.endswith("-vendedor.jpg") and segunda.endswith("-vendedor.webp")
    assert foto_do_vendedor(primeira) and foto_do_vendedor(segunda)
    pasta = Path(app.config["PASTA_DE_FOTOS"])
    assert (pasta / primeira.removeprefix("fotos/")).read_bytes() == JPEG
    assert (pasta / segunda.removeprefix("fotos/")).read_bytes() == WEBP

    servida = logado.get("/" + primeira)
    assert servida.status_code == 200 and servida.mimetype == "image/jpeg"
    servida.close()


def test_o_nome_e_o_tipo_que_o_navegador_manda_nao_decidem_a_extensao(logado, app, banco):
    criar_leilao(logado, app, fotos=[(io.BytesIO(IMAGEM_DE_TESTE), "../../carta.php", "text/html")])
    _, foto = fotos_da_carta(banco, leiloes_criados(banco)[0]["id"])
    assert foto.endswith("-vendedor.png") and "php" not in foto and ".." not in foto


def test_leilao_sem_fotos_do_vendedor_continua_sendo_criado(logado, app, banco):
    assert criar_leilao(logado, app).status_code == 303
    (foto,) = fotos_da_carta(banco, leiloes_criados(banco)[0]["id"])
    assert foto.endswith("-catalogo.png")


@pytest.mark.parametrize("fotos, mensagem", [
    ([b"isto nao e uma imagem"], "A foto 1 não é uma imagem JPEG, PNG ou WebP."),
    ([JPEG, b"GIF89a" + b"\x00" * 20], "A foto 2 não é uma imagem JPEG, PNG ou WebP."),
    ([JPEG] * (MAXIMO_DE_FOTOS + 1), f"Envie no máximo {MAXIMO_DE_FOTOS} fotos."),
    ([JPEG + b"\x00" * TAMANHO_MAXIMO_DA_FOTO], "A foto 1 passa de 8 MB. Envie uma foto menor."),
])
def test_foto_invalida_e_apontada_no_campo_e_nada_e_criado(logado, app, banco, fotos, mensagem):
    resposta = criar_leilao(logado, app, fotos=anexos(*fotos))
    pagina = resposta.get_data(as_text=True)
    assert resposta.status_code == 422 and mensagem in pagina
    assert 'id="erro-fotos"' in pagina and "escolha de novo" in pagina
    assert leiloes_criados(banco) == [] and arquivos(app) == []


def test_envio_maior_que_o_limite_da_loja_e_recusado_com_uma_pagina_de_erro(logado, app, banco):
    app.config["MAX_CONTENT_LENGTH"] = 1024
    resposta = criar_leilao(logado, app, fotos=anexos(JPEG + b"\x00" * 4096))
    assert resposta.status_code == 413 and "Arquivos grandes demais" in resposta.get_data(as_text=True)
    assert leiloes_criados(banco) == []


def test_outro_campo_invalido_nao_deixa_fotos_gravadas(logado, app, banco):
    assert criar_leilao(logado, app, lance_inicial="0", fotos=anexos(JPEG)).status_code == 422
    assert arquivos(app) == []


def test_lojista_ve_as_fotos_do_vendedor_ao_conferir_a_carta(logado, app, banco):
    criar_leilao(logado, app, fotos=anexos(JPEG, IMAGEM_DE_TESTE))
    numero = leiloes_criados(banco)[0]["id"]
    _, primeira, segunda = fotos_da_carta(banco, numero)
    admin = navegador_admin(app)

    for url in ("/admin/leiloes", f"/admin/cartas/{numero}"):
        pagina = admin.get(url).get_data(as_text=True)
        assert "Fotos tiradas pelo vendedor (2)" in pagina
        assert f'href="/{primeira}"' in pagina and f'href="/{segunda}"' in pagina
        assert "foto 2 tirada pelo vendedor" in pagina


def test_lojista_e_avisado_quando_o_vendedor_nao_mandou_fotos(logado, app, banco):
    criar_leilao(logado, app)
    numero = leiloes_criados(banco)[0]["id"]
    admin = navegador_admin(app)
    assert "O vendedor não enviou fotos da carta." in admin.get("/admin/leiloes").get_data(as_text=True)
    assert "O vendedor não enviou fotos desta carta." in admin.get(f"/admin/cartas/{numero}").get_data(as_text=True)


def test_anuncio_mostra_a_imagem_do_catalogo_e_as_fotos_do_vendedor(logado, app, banco):
    criar_leilao(logado, app, fotos=anexos(JPEG, WEBP))
    numero = leiloes_criados(banco)[0]["id"]
    aprovar_leilao(app, numero)
    catalogo, primeira, segunda = fotos_da_carta(banco, numero)

    pagina = app.test_client().get(f"/leiloes/{numero}").get_data(as_text=True)
    assert pagina.count('class="miniatura"') == 3
    assert "Charizard, Base Set (4/102): imagem do catálogo" in pagina
    assert "Charizard, Base Set (4/102): foto 1 tirada pelo vendedor" in pagina
    assert "Charizard, Base Set (4/102): foto 2 tirada pelo vendedor" in pagina
    assert f'src="/{catalogo}" alt="Charizard, Base Set (4/102): imagem do catálogo"' in pagina
    assert pagina.count("data-inteira") == 2
    assert f'data-url="/{catalogo}" data-descricao="Charizard, Base Set (4/102): imagem do catálogo">' in pagina

    lista = app.test_client().get("/leiloes").get_data(as_text=True)
    assert f'src="/{catalogo}"' in lista and primeira not in lista


def test_remover_o_cadastro_apaga_tambem_as_fotos_do_vendedor(logado, app, banco):
    criar_leilao(logado, app, fotos=anexos(JPEG, WEBP))
    numero = leiloes_criados(banco)[0]["id"]
    assert len(arquivos(app)) == 3
    navegador_admin(app).post(f"/admin/cartas/{numero}/remover", data={"csrf_token": CSRF})
    assert leiloes_criados(banco) == [] and arquivos(app) == []
