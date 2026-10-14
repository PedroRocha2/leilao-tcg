from decimal import Decimal

import pytest

from app.dominio.dinheiro import (
    ValorMonetarioInvalido,
    de_centavos,
    formatar_numero,
    formatar_reais,
    ler_reais,
    para_centavos,
)


@pytest.mark.parametrize(
    "texto, valor",
    [
        ("105", "105.00"),
        ("105,01", "105.01"),
        ("105,5", "105.50"),
        ("R$ 105,01", "105.01"),
        ("R$ 2.355,00", "2355.00"),
        ("  105,01  ", "105.01"),
        ("1.050,25", "1050.25"),
        ("1.050", "1050.00"),
        ("2.350.000,00", "2350000.00"),
        ("105.01", "105.01"),
        ("0,99", "0.99"),
        (",50", "0.50"),
    ],
)
def test_le_valores_no_formato_brasileiro(texto, valor):
    assert ler_reais(texto) == Decimal(valor)


@pytest.mark.parametrize("texto", ["", "   ", "abc", "10,999", "1,0,0", "-5", "1.05.0", "10.00.00", "12a", None])
def test_recusa_valores_mal_formatados(texto):
    with pytest.raises(ValorMonetarioInvalido):
        ler_reais(texto)


def test_formata_como_o_intl_number_format_pt_br():
    assert formatar_reais(Decimal("105.01")) == "R$ 105,01"
    assert formatar_reais(Decimal("2350")) == "R$ 2.350,00"
    assert formatar_reais(Decimal("0.05")) == "R$ 0,05"
    assert formatar_reais(Decimal("-20")) == "-R$ 20,00"
    assert formatar_numero(Decimal("2355")) == "2.355,00"


def test_converte_centavos_sem_ponto_flutuante():
    assert para_centavos(Decimal("2355.10")) == 235510
    assert de_centavos(235510) == Decimal("2355.10")
    assert de_centavos(para_centavos(Decimal("0.07"))) == Decimal("0.07")
