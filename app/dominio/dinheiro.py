import re
from decimal import ROUND_HALF_UP, Decimal

CENTAVO = Decimal("0.01")
NBSP = " "


class ValorMonetarioInvalido(ValueError):
    pass


_SO_DIGITOS = re.compile(r"^\d+$")
_MILHAR_COM_PONTO = re.compile(r"^\d{1,3}(\.\d{3})+$")


def reais(valor: Decimal | int | str) -> Decimal:
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def ler_reais(texto: str | None) -> Decimal:
    if texto is None:
        raise ValorMonetarioInvalido("Informe o valor do lance.")
    limpo = texto.strip().replace("R$", "").replace(" ", "").replace(NBSP, "")
    if not limpo:
        raise ValorMonetarioInvalido("Informe o valor do lance.")

    if "," in limpo:
        inteiro, _, decimal = limpo.rpartition(",")
        if inteiro and not (_SO_DIGITOS.match(inteiro) or _MILHAR_COM_PONTO.match(inteiro)):
            raise ValorMonetarioInvalido("Valor em formato inválido. Use, por exemplo, 2.355,00.")
        inteiro = inteiro.replace(".", "")
    elif _MILHAR_COM_PONTO.match(limpo):
        inteiro, decimal = limpo.replace(".", ""), ""
    elif "." in limpo:
        inteiro, _, decimal = limpo.partition(".")
    else:
        inteiro, decimal = limpo, ""

    inteiro = inteiro or "0"
    if not _SO_DIGITOS.match(inteiro) or (decimal and not _SO_DIGITOS.match(decimal)):
        raise ValorMonetarioInvalido("Valor em formato inválido. Use, por exemplo, 2.355,00.")
    if len(decimal) > 2:
        raise ValorMonetarioInvalido("Use no máximo duas casas decimais (centavos).")

    return Decimal(f"{int(inteiro)}.{decimal.ljust(2, '0')}")


def para_centavos(valor: Decimal) -> int:
    return int(reais(valor) * 100)


def de_centavos(centavos: int) -> Decimal:
    return reais(Decimal(centavos) / 100)


def formatar_numero(valor: Decimal) -> str:
    centavos = para_centavos(valor)
    inteiro, resto = divmod(abs(centavos), 100)
    sinal = "-" if centavos < 0 else ""
    return f"{sinal}{inteiro:,}".replace(",", ".") + f",{resto:02d}"


def formatar_reais(valor: Decimal) -> str:
    sinal = "-" if valor < 0 else ""
    return f"{sinal}R${NBSP}{formatar_numero(abs(valor))}"
