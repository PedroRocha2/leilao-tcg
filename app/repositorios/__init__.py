"""Repositórios: guardam e montam os objetos do domínio a partir do SQLite.

Todo o SQL da aplicação fica aqui. As rotas e o domínio só conhecem estes métodos, então trocar o
banco por uma API significa reescrever esta camada e nada mais.
"""

from app.repositorios.clientes import RepositorioClientes
from app.repositorios.leiloes import RepositorioLeiloes

__all__ = ["RepositorioClientes", "RepositorioLeiloes"]
