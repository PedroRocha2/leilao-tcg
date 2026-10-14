"""CPF do Cliente: validação pelos dígitos verificadores (algoritmo da Receita Federal)."""

import re

_SO_PERMITIDOS = re.compile(r"^[\d.\-\s]+$")


def somente_digitos(texto: str | None) -> str:
    return re.sub(r"\D", "", texto or "")


def _digito_verificador(base: str) -> str:
    """Pesos decrescentes até 2; resto 10 vira 0."""
    peso = len(base) + 1
    soma = sum(int(digito) * (peso - posicao) for posicao, digito in enumerate(base))
    return str(soma * 10 % 11 % 10)


def cpf_valido(texto: str | None) -> bool:
    """Aceita com ou sem pontuação ("529.982.247-25" ou "52998224725")."""
    if not texto or not _SO_PERMITIDOS.match(texto):
        return False
    numeros = somente_digitos(texto)
    if len(numeros) != 11 or numeros == numeros[0] * 11:
        return False
    return (numeros[9] == _digito_verificador(numeros[:9])
            and numeros[10] == _digito_verificador(numeros[:10]))


def completar_cpf(nove_digitos: str) -> str:
    """Acrescenta os dois dígitos verificadores a uma base de 9 dígitos."""
    base = somente_digitos(nove_digitos)
    if len(base) != 9:
        raise ValueError("A base do CPF tem 9 dígitos.")
    base += _digito_verificador(base)
    return base + _digito_verificador(base)


def formatar_cpf(numeros: str) -> str:
    """"52998224725" -> "529.982.247-25"."""
    return f"{numeros[:3]}.{numeros[3:6]}.{numeros[6:9]}-{numeros[9:]}"


def mascarar_cpf(numeros: str) -> str:
    """"52998224725" -> "***.982.247-**": a tela não precisa mostrar o CPF inteiro (LGPD)."""
    return f"***.{numeros[3:6]}.{numeros[6:9]}-**"
