import sqlite3
import threading
from datetime import timedelta
from decimal import Decimal

import pytest

from apoio import (AGORA, avancar_relogio, criar_conta, lance_json, leilao_id, novo_cliente, novo_leilao,
                   outro_navegador)
from app.carga_inicial import CLIENTES
from app.db import agora_utc, para_texto
from app.dominio.financeiro import StatusTransacao
from app.dominio.leiloes import Lance, LanceRecusado, MotivoRecusa, StatusCarta, StatusLeilao
from app.andamento import encerrar_leiloes_vencidos
from app.repositorios import RepositorioLeiloes

VALOR = Decimal
FIM = AGORA + timedelta(days=1)


@pytest.fixture
def vendedor():
    return novo_cliente(1, "100200300")


@pytest.fixture
def ana():
    return novo_cliente(2, "200300400")


@pytest.fixture
def bruno():
    return novo_cliente(3, "300400500")


@pytest.fixture
def leilao(vendedor):
    return novo_leilao(vendedor, fim=FIM)


def test_encerrar_gera_o_arremate_para_o_maior_lance(leilao, vendedor, ana, bruno):
    ana.darLance(leilao, VALOR("100.00"), AGORA)
    bruno.darLance(leilao, VALOR("150.00"), AGORA + timedelta(minutes=1))
    ana.darLance(leilao, VALOR("155.00"), AGORA + timedelta(minutes=2))

    arremate = leilao.encerrar(FIM)

    assert leilao.status == StatusLeilao.ENCERRADO
    assert leilao.transacao is arremate
    assert arremate.comprador is ana and arremate.vendedor is vendedor
    assert arremate.valor == VALOR("155.00")
    assert arremate.status == StatusTransacao.AGUARDANDO_PAGAMENTO
    assert leilao.carta.status == StatusCarta.ARREMATADA


def test_encerrar_registra_o_fim_do_prazo_e_nao_o_instante_do_processamento(leilao, ana):
    ana.darLance(leilao, VALOR("100.00"), AGORA)
    arremate = leilao.encerrar(FIM + timedelta(hours=2))
    assert leilao.dataFimReal == FIM
    assert arremate.dataHora == FIM


def test_encerrar_sem_lances_nao_gera_arremate_e_devolve_a_carta(leilao):
    assert leilao.encerrar(FIM) is None
    assert leilao.status == StatusLeilao.ENCERRADO and leilao.dataFimReal == FIM
    assert leilao.transacao is None
    assert leilao.carta.status == StatusCarta.DEVOLVIDA_AO_VENDEDOR


def test_nao_encerra_antes_do_fim_do_prazo(leilao, ana):
    ana.darLance(leilao, VALOR("100.00"), AGORA)
    with pytest.raises(ValueError, match="prazo"):
        leilao.encerrar(FIM - timedelta(milliseconds=1))
    assert leilao.status == StatusLeilao.ATIVO
    assert leilao.dataFimReal is None and leilao.transacao is None
    assert leilao.carta.status == StatusCarta.EM_LEILAO


def test_encerra_no_instante_exato_do_fim_do_prazo(leilao, ana):
    """O mesmo instante em que a RN12 passa a recusar lances."""
    ana.darLance(leilao, VALOR("100.00"), AGORA)
    assert leilao.validarLance(VALOR("500.00"), FIM) is False
    assert leilao.encerrar(FIM) is not None


@pytest.mark.parametrize("status", [StatusLeilao.PENDENTE, StatusLeilao.APROVADO,
                                    StatusLeilao.ENCERRADO, StatusLeilao.CANCELADO])
def test_so_leilao_ativo_e_encerrado(vendedor, status):
    leilao = novo_leilao(vendedor, fim=FIM, status=status)
    with pytest.raises(ValueError, match="ativo"):
        leilao.encerrar(FIM)
    assert leilao.status == status and leilao.transacao is None


def test_encerrar_duas_vezes_nao_gera_outro_arremate(leilao, ana):
    ana.darLance(leilao, VALOR("100.00"), AGORA)
    arremate = leilao.encerrar(FIM)
    with pytest.raises(ValueError, match="ativo"):
        leilao.encerrar(FIM + timedelta(minutes=1))
    assert leilao.transacao is arremate


def test_empate_de_valor_arremata_quem_deu_o_lance_primeiro(leilao, ana, bruno):
    """RN13 no encerramento."""
    depois = Lance(valor=VALOR("200.00"), dataHora=AGORA + timedelta(milliseconds=5), cliente=bruno)
    antes = Lance(valor=VALOR("200.00"), dataHora=AGORA + timedelta(milliseconds=4), cliente=ana)
    leilao.lances.extend([depois, antes])
    assert leilao.encerrar(FIM).comprador is ana


def test_lance_que_prorroga_o_prazo_adia_o_encerramento(vendedor, ana):
    """RN02: o leilão só encerra no fim do prazo prorrogado."""
    fim = AGORA + timedelta(minutes=2)
    leilao = novo_leilao(vendedor, fim=fim)
    ana.darLance(leilao, VALOR("100.00"), AGORA)
    with pytest.raises(ValueError, match="prazo"):
        leilao.encerrar(fim)
    leilao.encerrar(fim + timedelta(minutes=3))
    assert leilao.dataFimReal == fim + timedelta(minutes=3)


def test_leilao_encerrado_nao_recebe_lance_e_diz_por_que(leilao, ana, bruno):
    ana.darLance(leilao, VALOR("100.00"), AGORA)
    leilao.encerrar(FIM)
    with pytest.raises(LanceRecusado) as erro:
        bruno.darLance(leilao, VALOR("500.00"), FIM + timedelta(seconds=1))
    assert erro.value.motivo is MotivoRecusa.LEILAO_INATIVO
    assert "já foi encerrado" in erro.value.mensagem
    assert leilao.transacao.comprador is ana


@pytest.fixture
def repositorio(banco):
    return RepositorioLeiloes(banco)


@pytest.fixture
def charizard(banco):
    return leilao_id(banco, "Charizard")


@pytest.fixture
def logado(cliente_http):
    criar_conta(cliente_http)
    return cliente_http


def status_dos_leiloes(banco) -> dict[str, str]:
    return {linha["nome"]: linha["status"] for linha in banco.execute(
        "SELECT c.nome, l.status FROM leiloes l JOIN cartas c ON c.id = l.carta_id")}


def transacoes(banco, id_do_leilao=None) -> list[sqlite3.Row]:
    if id_do_leilao is None:
        return banco.execute("SELECT * FROM transacoes ORDER BY id").fetchall()
    return banco.execute("SELECT * FROM transacoes WHERE leilao_id = ?", (id_do_leilao,)).fetchall()


def test_servico_encerra_so_os_leiloes_com_o_prazo_terminado(repositorio, banco):
    """Na carga, o Dark Magician termina em 25 minutos e o Counterspell em 45."""
    encerrados = encerrar_leiloes_vencidos(repositorio, agora_utc() + timedelta(minutes=30))
    assert [leilao.carta.nome for leilao in encerrados] == ["Dark Magician"]
    status = status_dos_leiloes(banco)
    assert status.pop("Dark Magician") == "encerrado"
    assert set(status.values()) == {"ativo"} and len(status) == 14
    assert len(transacoes(banco)) == 1


def test_servico_nao_encerra_nem_arremata_duas_vezes(repositorio, banco):
    momento = agora_utc() + timedelta(minutes=30)
    encerrar_leiloes_vencidos(repositorio, momento)
    assert encerrar_leiloes_vencidos(repositorio, momento) == []
    assert len(transacoes(banco)) == 1


def test_encerramento_e_recarregado_do_banco_com_o_arremate(repositorio, banco):
    encerrar_leiloes_vencidos(repositorio, agora_utc() + timedelta(minutes=30))
    leilao = repositorio.por_id(leilao_id(banco, "Dark Magician"))
    assert leilao.status == StatusLeilao.ENCERRADO and leilao.dataFimReal == leilao.dataFimPrevista
    assert leilao.carta.status == StatusCarta.ARREMATADA
    arremate = leilao.transacao
    assert arremate.id is not None and arremate.valor == VALOR("155.00")
    assert arremate.comprador.ehOMesmo(leilao.getMaiorLance().cliente)
    assert arremate.vendedor.ehOMesmo(leilao.carta.vendedor)
    assert arremate.dataHora == leilao.dataFimReal


def test_banco_recusa_segundo_arremate_do_mesmo_leilao(repositorio, banco):
    encerrar_leiloes_vencidos(repositorio, agora_utc() + timedelta(minutes=30))
    gravada = transacoes(banco)[0]
    with pytest.raises(sqlite3.IntegrityError):
        banco.execute(
            "INSERT INTO transacoes (leilao_id, comprador_id, valor_centavos, data_hora, status, taxa_centavos,"
            " liquido_centavos, codigo_retirada, prazo_pagamento) VALUES (?, ?, ?, ?, ?, 0, ?, 'OUTROCOD', ?)",
            (gravada["leilao_id"], gravada["comprador_id"], 100, gravada["data_hora"], gravada["status"], 100,
             gravada["prazo_pagamento"]),
        )


def test_leilao_e_encerrado_sozinho_quando_o_prazo_termina(app, cliente_http, banco, charizard):
    """Charizard termina 5 h 50 min depois da carga; antes dele, Dark Magician e Counterspell."""
    assert cliente_http.get("/leiloes").get_data(as_text=True).count('class="cartao"') == 15
    assert transacoes(banco) == []

    avancar_relogio(app, hours=6)
    assert cliente_http.get("/leiloes").get_data(as_text=True).count('class="cartao"') == 12

    leilao = banco.execute("SELECT * FROM leiloes WHERE id = ?", (charizard,)).fetchone()
    assert leilao["status"] == "encerrado"
    assert leilao["data_fim_real"] == leilao["data_fim_prevista"]
    carta = banco.execute("SELECT status FROM cartas WHERE id = ?", (leilao["carta_id"],)).fetchone()
    assert carta["status"] == "arrematada"

    maior = banco.execute(
        "SELECT cliente_id, valor_centavos FROM lances WHERE leilao_id = ? ORDER BY valor_centavos DESC LIMIT 1",
        (charizard,)).fetchone()
    (arremate,) = transacoes(banco, charizard)
    assert arremate["comprador_id"] == maior["cliente_id"]
    assert arremate["valor_centavos"] == maior["valor_centavos"] == 235000
    assert arremate["data_hora"] == leilao["data_fim_real"]
    assert arremate["status"] == "aguardando pagamento"
    assert len(transacoes(banco)) == 3


def test_leilao_sem_lances_encerra_sem_arremate_e_a_carta_volta_ao_vendedor(app, cliente_http, banco):
    mewtwo = leilao_id(banco, "Mewtwo")
    avancar_relogio(app, days=3, hours=3)
    pagina = cliente_http.get(f"/leiloes/{mewtwo}").get_data(as_text=True)

    assert "Leilão encerrado sem lances. A carta não foi arrematada." in pagina
    assert "Este leilão não recebeu lances." in pagina
    assert "Ninguém deu lance ainda" not in pagina
    linha = banco.execute(
        "SELECT l.status, c.status AS carta FROM leiloes l JOIN cartas c ON c.id = l.carta_id WHERE l.id = ?",
        (mewtwo,)).fetchone()
    assert (linha["status"], linha["carta"]) == ("encerrado", "devolvida ao vendedor")
    assert transacoes(banco, mewtwo) == []


def test_leilao_cancelado_nao_e_encerrado_nem_gera_arremate(app, cliente_http, banco):
    kuriboh = leilao_id(banco, "Kuriboh")
    banco.execute("UPDATE leiloes SET status = 'cancelado' WHERE id = ?", (kuriboh,))
    avancar_relogio(app, days=10)
    cliente_http.get("/leiloes")

    status = status_dos_leiloes(banco)
    assert status.pop("Kuriboh") == "cancelado"
    assert set(status.values()) == {"encerrado"}
    assert transacoes(banco, kuriboh) == []
    assert len(transacoes(banco)) == 11


def test_pagina_do_leilao_encerrado_mostra_o_resultado_sem_identificar_o_vencedor(app, cliente_http, charizard):
    avancar_relogio(app, hours=6)
    pagina = cliente_http.get(f"/leiloes/{charizard}").get_data(as_text=True)

    assert "Licitante 1 arrematou esta carta por R$ 2.350,00." in pagina
    assert "Valor do arremate" in pagina and "Lance vencedor" in pagina
    assert "Encerrado" in pagina and "Fim do prazo" in pagina
    for ausente in ("data-form-lance", "Entrar para dar lance", "Maior lance", "Ver meus arremates"):
        assert ausente not in pagina
    for nome, *_ in CLIENTES:
        assert nome not in pagina


def test_estado_json_do_leilao_encerrado_traz_o_resultado(app, cliente_http, charizard):
    avancar_relogio(app, hours=6)
    estado = cliente_http.get(f"/leiloes/{charizard}/estado").get_json()["estado"]
    assert estado["aberto"] is False and estado["situacao"] == "Encerrado"
    assert estado["arrematado"] is True and estado["voce_arrematou"] is False
    assert estado["rotulo_valor"] == "Valor do arremate" and estado["valor_centavos"] == 235000
    assert estado["resultado"] == "Licitante 1 arrematou esta carta por R$ 2.350,00."


def test_quem_deu_o_maior_lance_arremata_e_ve_o_arremate_em_minha_conta(app, logado, banco, charizard):
    assert "Você ainda não arrematou nenhuma carta." in logado.get("/minha-conta/arremates").get_data(as_text=True)
    assert lance_json(logado, charizard, "2.355,00").status_code == 201

    avancar_relogio(app, hours=6)
    pagina = logado.get(f"/leiloes/{charizard}").get_data(as_text=True)
    assert "Você arrematou esta carta por R$ 2.355,00." in pagina
    assert 'href="/minha-conta/arremates"' in pagina and "data-form-lance" not in pagina

    ana = banco.execute("SELECT id FROM usuarios WHERE email = ?", ("ana@teste.com",)).fetchone()["id"]
    (arremate,) = transacoes(banco, charizard)
    assert (arremate["comprador_id"], arremate["valor_centavos"]) == (ana, 235500)

    arremates = logado.get("/minha-conta/arremates").get_data(as_text=True)
    assert 'href="/minha-conta/arremates" aria-current="page"' in arremates
    for trecho in (">Charizard</a>", "Base Set (4/102)", "R$ 2.355,00", "Aguardando pagamento"):
        assert trecho in arremates
    assert arremates.count('class="meu-lance"') == 1
    assert "Você arrematou" in logado.get("/minha-conta/lances").get_data(as_text=True)


def test_quem_foi_superado_nao_arremata(app, logado, charizard):
    lance_json(logado, charizard, "2.355,00")
    bruno = outro_navegador(app)
    lance_json(bruno, charizard, "2.400,00")

    avancar_relogio(app, hours=6)
    pagina = logado.get(f"/leiloes/{charizard}").get_data(as_text=True)
    assert "arrematou esta carta por R$ 2.400,00." in pagina and "Você arrematou" not in pagina
    assert "Você ainda não arrematou nenhuma carta." in logado.get("/minha-conta/arremates").get_data(as_text=True)
    meus_lances = logado.get("/minha-conta/lances").get_data(as_text=True)
    assert "Superado" in meus_lances and "Você arrematou" not in meus_lances
    assert ">Charizard</a>" in bruno.get("/minha-conta/arremates").get_data(as_text=True)


def test_lance_depois_do_encerramento_e_recusado_e_nao_muda_o_arremate(app, logado, banco, charizard):
    avancar_relogio(app, hours=6)
    resposta = lance_json(logado, charizard, "9.999,00")
    assert resposta.status_code == 422
    corpo = resposta.get_json()
    assert corpo["motivo"] == "leilao_inativo" and "já foi encerrado" in corpo["mensagem"]
    assert corpo["estado"]["resultado"] == "Licitante 1 arrematou esta carta por R$ 2.350,00."
    (arremate,) = transacoes(banco, charizard)
    assert arremate["valor_centavos"] == 235000


def test_lance_nos_ultimos_minutos_adia_o_encerramento(app, logado, banco, charizard):
    """RN02 com RF09: o prazo prorrogado é o que vale para encerrar."""
    fim = agora_utc() + timedelta(minutes=2)
    banco.execute("UPDATE leiloes SET data_fim_prevista = ? WHERE id = ?", (para_texto(fim), charizard))
    assert lance_json(logado, charizard, "2.355,00").status_code == 201

    avancar_relogio(app, minutes=3)
    assert logado.get(f"/leiloes/{charizard}/estado").get_json()["estado"]["aberto"] is True
    assert status_dos_leiloes(banco)["Charizard"] == "ativo"

    avancar_relogio(app, minutes=6)
    estado = logado.get(f"/leiloes/{charizard}/estado").get_json()["estado"]
    assert estado["voce_arrematou"] is True
    leilao = banco.execute("SELECT data_fim_real FROM leiloes WHERE id = ?", (charizard,)).fetchone()
    assert leilao["data_fim_real"] == para_texto(fim + timedelta(minutes=3))


def test_pedidos_simultaneos_geram_um_unico_arremate_por_leilao(app, banco, charizard):
    avancar_relogio(app, hours=6)
    largada = threading.Barrier(4)
    respostas = []

    def visitar():
        navegador = app.test_client()
        largada.wait()
        respostas.append(navegador.get("/leiloes").status_code)

    threads = [threading.Thread(target=visitar) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert respostas == [200] * 4
    assert len(transacoes(banco, charizard)) == 1
    assert len(transacoes(banco)) == 3


def test_arremates_exige_login(cliente_http):
    resposta = cliente_http.get("/minha-conta/arremates")
    assert resposta.status_code == 302
    assert resposta.headers["Location"].startswith("/entrar?proximo=")
