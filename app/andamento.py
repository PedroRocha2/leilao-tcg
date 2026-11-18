"""Mudanças que dependem só do relógio."""
from datetime import datetime, timedelta

from app.db import transacao
from app.dominio.leiloes import PRAZO_DE_PAGAMENTO, Leilao, StatusCarta
from app.repositorios.clientes import RepositorioClientes
from app.repositorios.leiloes import RepositorioLeiloes


def iniciar_leiloes_aprovados(repositorio: RepositorioLeiloes, agora: datetime) -> list[Leilao]:
    """RN12."""
    return _aplicar(repositorio, lambda: repositorio.a_iniciar(agora),
                    lambda leilao: leilao.iniciar(agora), repositorio.salvar_status)


def encerrar_leiloes_vencidos(repositorio: RepositorioLeiloes, agora: datetime,
                              prazo_de_pagamento: timedelta = PRAZO_DE_PAGAMENTO) -> list[Leilao]:
    return _aplicar(repositorio, lambda: repositorio.vencidos(agora),
                    lambda leilao: leilao.encerrar(agora, prazo_de_pagamento), repositorio.salvar_encerramento)


def expirar_pagamentos(leiloes: RepositorioLeiloes, clientes: RepositorioClientes,
                       agora: datetime) -> list[Leilao]:
    """RN06 e RF21: descumprimento para o comprador e carta de volta ao vendedor."""
    def expirar(leilao: Leilao) -> None:
        leilao.transacao.expirar(agora)
        leilao.transacao.comprador.registrarDescumprimento()
        leilao.carta.atualizarStatus(StatusCarta.DEVOLVIDA_AO_VENDEDOR)

    def salvar(leilao: Leilao) -> None:
        leiloes.salvar_transacao(leilao)
        clientes.atualizar(leilao.transacao.comprador)

    return _aplicar(leiloes, lambda: leiloes.com_pagamento_vencido(agora), expirar, salvar)


def _aplicar(repositorio, selecionar, mudar, salvar) -> list[Leilao]:
    if not selecionar():
        return []
    with transacao(repositorio.conexao, imediata=True):
        # Relê com o banco travado: outro pedido, um lance (RN02) ou um pagamento pode ter mudado o leilão.
        leiloes = selecionar()
        for leilao in leiloes:
            mudar(leilao)
            salvar(leilao)
    return leiloes
