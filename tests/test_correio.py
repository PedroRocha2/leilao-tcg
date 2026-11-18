"""O e-mail com o código de retirada, mandado quando o pagamento do arremate é confirmado.

Nenhum teste usa a rede: `CorreioFalso` guarda os e-mails e `ServidorFalso` faz o papel do smtplib.
"""
import smtplib

import pytest

from apoio import (CSRF, ITERACOES_DE_TESTE, CorreioFalso, aprovar_leilao, avancar_relogio, catalogo_de_teste,
                   criar_conta, criar_leilao, lance_json, leiloes_criados, outro_navegador)
from app import create_app
from app.correio import CorreioIndisponivel, CorreioLocal, CorreioSMTP
from app.dominio.dinheiro import formatar_reais


@pytest.fixture
def correio(app):
    app.config["CORREIO"] = CorreioFalso()
    return app.config["CORREIO"]


@pytest.fixture
def arremate(app, cliente_http, banco):
    """Ana vende o Charizard e Bruno arremata por R$ 200,00. Devolve o número do leilão e o navegador dele."""
    criar_conta(cliente_http)
    criar_leilao(cliente_http, app, lance_inicial="100,00")
    numero = leiloes_criados(banco)[0]["id"]
    aprovar_leilao(app, numero)
    bruno = outro_navegador(app)
    assert lance_json(bruno, numero, "200,00").status_code == 201
    avancar_relogio(app, days=3, hours=1)
    bruno.get("/minha-conta/arremates")
    return numero, bruno


def pagar(navegador, numero, **dados):
    return navegador.post(f"/minha-conta/arremates/{numero}/pagar",
                          data={"csrf_token": CSRF, "forma": "pix", **dados})


def transacao_de(banco, numero):
    return banco.execute("SELECT * FROM transacoes WHERE leilao_id = ?", (numero,)).fetchone()


def test_sem_servidor_smtp_a_loja_nao_manda_email(tmp_path, monkeypatch):
    opcoes = {"TESTING": True, "DATABASE": str(tmp_path / "b.sqlite3"), "SECRET_KEY": "x",
              "PBKDF2_ITERACOES": ITERACOES_DE_TESTE, "CATALOGO": catalogo_de_teste(), "MERCADO_PAGO_TOKEN": ""}
    local = create_app(opcoes).config["CORREIO"]
    assert isinstance(local, CorreioLocal) and not local.externo
    assert local.enviar("bruno@teste.com", "Assunto", "Texto") is None

    monkeypatch.setenv("LEILAO_SMTP_SERVIDOR", " smtp.exemplo.com ")
    monkeypatch.setenv("LEILAO_SMTP_USUARIO", "loja@exemplo.com")
    monkeypatch.setenv("LEILAO_SMTP_SENHA", "senha de app")
    correio = create_app(opcoes).config["CORREIO"]
    assert isinstance(correio, CorreioSMTP) and correio.externo


def test_servidor_smtp_sem_remetente_nem_usuario_nao_sobe():
    with pytest.raises(ValueError, match="remetente"):
        CorreioSMTP("smtp.exemplo.com")


def test_pagamento_confirmado_manda_o_codigo_de_retirada_ao_comprador(arremate, correio, banco):
    numero, bruno = arremate
    assert pagar(bruno, numero).status_code == 303

    codigo = transacao_de(banco, numero)["codigo_retirada"]
    ((destinatario, assunto, texto),) = correio.enviados
    assert destinatario == "bruno@teste.com"
    assert assunto == "Pagamento confirmado: Charizard" and codigo not in assunto
    for trecho in ("Olá, Ana Souza.",
                   f"pagamento de {formatar_reais(200)} pelo arremate de Charizard, Base Set (4/102).",
                   f"Código de retirada: {codigo}", "Apresente este código no balcão da loja"):
        assert trecho in texto
    # Sem endereço público, o e-mail não leva um link que só abriria na máquina da loja.
    assert "http" not in texto


def test_email_leva_o_endereco_de_arremates_quando_a_loja_tem_endereco_publico(app, arremate, correio):
    numero, bruno = arremate
    app.config["URL_PUBLICA"] = "https://loja.exemplo.com"
    pagar(bruno, numero)
    assert "Minha Conta > Arremates: https://loja.exemplo.com/minha-conta/arremates" in correio.enviados[0][2]


def test_pagamento_com_o_saldo_da_carteira_tambem_manda_o_email(arremate, correio, banco):
    numero, bruno = arremate
    banco.execute("UPDATE carteiras SET saldo_centavos = 30000 WHERE cliente_id = (SELECT id FROM usuarios"
                  " WHERE email = 'bruno@teste.com')")
    assert pagar(bruno, numero, usar_saldo="sim", forma="").status_code == 303
    assert [destinatario for destinatario, _, _ in correio.enviados] == ["bruno@teste.com"]


def test_pagamento_recusado_ou_repetido_nao_manda_email(arremate, correio, banco):
    numero, bruno = arremate
    assert pagar(bruno, numero, forma="boleto").status_code == 422
    assert correio.enviados == []

    pagar(bruno, numero)
    assert pagar(bruno, numero).status_code == 302
    assert len(correio.enviados) == 1


def test_falha_no_envio_do_email_nao_desfaz_o_pagamento(arremate, correio, banco):
    numero, bruno = arremate
    correio.fora_do_ar = True
    resposta = pagar(bruno, numero)
    assert (resposta.status_code, resposta.headers["Location"]) == (303, "/minha-conta/arremates")

    paga = transacao_de(banco, numero)
    assert paga["status"] == "pago"
    pagina = bruno.get("/minha-conta/arremates").get_data(as_text=True)
    assert f"Retire Charizard na loja com o código {paga['codigo_retirada']}." in pagina
    assert correio.enviados == []


class ServidorFalso:
    """Faz o papel de smtplib.SMTP e smtplib.SMTP_SSL: anota o que a loja pediu, sem abrir conexão."""

    def __init__(self):
        self.passos: list = []
        self.mensagens: list = []
        self.oferece_starttls = True
        self.fora_do_ar = False
        self.recusa_do_login: Exception | None = None

    def conexao(self, cifrada: bool):
        servidor = self

        class Conexao:
            def __init__(self, endereco, porta, timeout=None, context=None):
                assert timeout
                if servidor.fora_do_ar:
                    raise OSError("sem rede (teste)")
                servidor.passos.append(("ssl" if cifrada else "conectar", endereco, porta))

            def __enter__(self):
                return self

            def __exit__(self, *erro):
                servidor.passos.append("sair")

            def ehlo(self):
                pass

            def has_extn(self, nome):
                return nome == "starttls" and servidor.oferece_starttls

            def starttls(self, context=None):
                assert context is not None
                servidor.passos.append("starttls")

            def login(self, usuario, senha):
                if servidor.recusa_do_login:
                    raise servidor.recusa_do_login
                servidor.passos.append(("login", usuario, senha))

            def send_message(self, mensagem):
                servidor.mensagens.append(mensagem)

            def close(self):
                servidor.passos.append("fechar")

        return Conexao


@pytest.fixture
def servidor(monkeypatch):
    falso = ServidorFalso()
    monkeypatch.setattr(smtplib, "SMTP", falso.conexao(cifrada=False))
    monkeypatch.setattr(smtplib, "SMTP_SSL", falso.conexao(cifrada=True))
    return falso


def test_smtp_cifra_a_conexao_entra_com_a_senha_e_manda_a_mensagem(servidor):
    CorreioSMTP("smtp.exemplo.com", 587, "loja@exemplo.com", "senha", "Leilão TCG <loja@exemplo.com>").enviar(
        "bruno@teste.com", "Pagamento confirmado: Pokémon", "Código de retirada: ABCD2345\n")

    assert servidor.passos == [("conectar", "smtp.exemplo.com", 587), "starttls",
                               ("login", "loja@exemplo.com", "senha"), "sair"]
    (mensagem,) = servidor.mensagens
    assert (mensagem["From"], mensagem["To"]) == ("Leilão TCG <loja@exemplo.com>", "bruno@teste.com")
    assert mensagem["Subject"] == "Pagamento confirmado: Pokémon"
    assert mensagem.get_content() == "Código de retirada: ABCD2345\n"


def test_smtp_na_porta_465_ja_abre_a_conexao_cifrada_e_o_remetente_e_o_usuario(servidor):
    CorreioSMTP("smtp.exemplo.com", 465, "loja@exemplo.com", "senha").enviar("bruno@teste.com", "Assunto", "Texto")
    assert servidor.passos == [("ssl", "smtp.exemplo.com", 465), ("login", "loja@exemplo.com", "senha"), "sair"]
    assert servidor.mensagens[0]["From"] == "loja@exemplo.com"


def test_smtp_nao_manda_a_senha_por_conexao_aberta(servidor):
    servidor.oferece_starttls = False
    with pytest.raises(CorreioIndisponivel, match="STARTTLS"):
        CorreioSMTP("smtp.exemplo.com", 25, "loja@exemplo.com", "senha").enviar("bruno@teste.com", "Assunto", "Texto")
    assert servidor.passos == [("conectar", "smtp.exemplo.com", 25), "fechar"] and servidor.mensagens == []

    CorreioSMTP("localhost", 25, remetente="loja@exemplo.com").enviar("bruno@teste.com", "Assunto", "Texto")
    assert servidor.passos[2:] == [("conectar", "localhost", 25), "sair"] and len(servidor.mensagens) == 1


def test_smtp_fora_do_ar_ou_recusando_a_senha_vira_correio_indisponivel(servidor):
    correio = CorreioSMTP("smtp.exemplo.com", 587, "loja@exemplo.com", "senha")
    servidor.fora_do_ar = True
    with pytest.raises(CorreioIndisponivel, match="smtp.exemplo.com"):
        correio.enviar("bruno@teste.com", "Assunto", "Texto")

    servidor.fora_do_ar = False
    servidor.recusa_do_login = smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
    with pytest.raises(CorreioIndisponivel, match="535"):
        correio.enviar("bruno@teste.com", "Assunto", "Texto")
    assert servidor.mensagens == []


def test_assunto_com_quebra_de_linha_nao_cria_cabecalho(servidor):
    CorreioSMTP("smtp.exemplo.com", 587, "loja@exemplo.com", "senha").enviar(
        "bruno@teste.com", "Pagamento confirmado: Carta\r\nBcc: outro@exemplo.com", "Texto")
    (mensagem,) = servidor.mensagens
    assert mensagem["Subject"] == "Pagamento confirmado: Carta Bcc: outro@exemplo.com"
    assert mensagem["Bcc"] is None
