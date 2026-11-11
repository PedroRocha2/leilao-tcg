"""O que o relógio faz sozinho: iniciar leilões aprovados, encerrar os que terminaram e expirar pagamentos."""
from datetime import datetime, timedelta

from app.db import transacao
from app.dominio.leiloes import PRAZO_DE_PAGAMENTO, Leilao, StatusCarta
from app.repositorios.clientes import RepositorioClientes
from app.repositorios.leiloes import RepositorioLeiloes


def iniciar_leiloes_aprovados(repositorio: RepositorioLeiloes, agora: datetime) -> list[Leilao]:
    """Põe em andamento os leilões aprovados cuja data de início chegou (RN12)."""
    return _aplicar(repositorio, lambda: repositorio.a_iniciar(agora),
                    lambda leilao: leilao.iniciar(agora), repositorio.salvar_status)


def encerrar_leiloes_vencidos(repositorio: RepositorioLeiloes, agora: datetime,
                              prazo_de_pagamento: timedelta = PRAZO_DE_PAGAMENTO) -> list[Leilao]:
    """Encerra os leilões ativos cujo prazo terminou e grava o arremate dos que receberam lances."""
    return _aplicar(repositorio, lambda: repositorio.vencidos(agora),
                    lambda leilao: leilao.encerrar(agora, prazo_de_pagamento), repositorio.salvar_encerramento)


def expirar_pagamentos(leiloes: RepositorioLeiloes, clientes: RepositorioClientes,
                       agora: datetime) -> list[Leilao]:
    """RN06 e RF21: arremate não pago no prazo marca um descumprimento e devolve a carta ao vendedor."""
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
        # Relê com o banco travado: enquanto esperava a trava, outro pedido pode ter feito a mesma
        # mudança, um lance pode ter prorrogado o prazo (RN02) ou o comprador pode ter pago.
        leiloes = selecionar()
        for leilao in leiloes:
            mudar(leilao)
            salvar(leilao)
    return leiloes
