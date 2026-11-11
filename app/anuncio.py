from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.catalogo import EXTENSOES, CartaDoCatalogo, Catalogo
from app.db import transacao
from app.dominio.contas import Cliente
from app.dominio.dinheiro import ValorMonetarioInvalido, ler_reais
from app.dominio.leiloes import CONDICOES, Leilao
from app.dominio.loja import ConfiguracaoLoja
from app.repositorios.leiloes import RepositorioLeiloes

PREFIXO_DAS_FOTOS = "fotos/"
TAMANHO_DA_DESCRICAO = 1000
# O formulário vem preenchido com o horário em que foi aberto; quem demora para enviar não é barrado.
TOLERANCIA_DO_INICIO = timedelta(minutes=15)


@dataclass
class AnuncioInvalido(Exception):
    erros: dict[str, str] = field(default_factory=dict)


def ler_data_hora(texto: str | None, fuso: ZoneInfo) -> datetime | None:
    """A data e a hora de um campo datetime-local, no fuso da loja."""
    try:
        return datetime.fromisoformat(texto or "").replace(tzinfo=fuso)
    except ValueError:
        return None


def anunciar_carta(leiloes: RepositorioLeiloes, catalogo: Catalogo, vendedor: Cliente, pasta_de_fotos: Path, *,
                   carta: CartaDoCatalogo, edicao: str, condicao: str, descricao: str, lance_inicial: str,
                   inicio: str, fim: str, agora: datetime, fuso: ZoneInfo,
                   configuracao: ConfiguracaoLoja) -> Leilao:
    """RF03: cadastra a carta escolhida no catálogo e cria o leilão dela, que nasce pendente (RN12)."""
    erros: dict[str, str] = {}

    edicao = carta.edicoes[0] if len(carta.edicoes) == 1 else (edicao or "").strip()
    if edicao not in carta.edicoes:
        erros["edicao"] = "Escolha a edição da sua carta."
    if condicao not in CONDICOES:
        erros["condicao"] = "Escolha a condição da carta."

    descricao = " ".join((descricao or "").split())
    if not descricao:
        erros["descricao"] = "Descreva a carta e o estado em que ela está."
    elif len(descricao) > TAMANHO_DA_DESCRICAO:
        erros["descricao"] = f"Use no máximo {TAMANHO_DA_DESCRICAO} caracteres."

    valor = None
    try:
        valor = ler_reais(lance_inicial)
    except ValorMonetarioInvalido as erro:
        erros["lance_inicial"] = str(erro).replace("valor do lance", "lance mínimo inicial")
    if valor is not None and valor <= 0:
        erros["lance_inicial"] = "Informe um valor maior que zero, como 50,00."

    data_inicio, data_fim = ler_data_hora(inicio, fuso), ler_data_hora(fim, fuso)
    if data_inicio is None:
        erros["inicio"] = "Informe a data e a hora de início."
    elif data_inicio < agora - TOLERANCIA_DO_INICIO:
        erros["inicio"] = "A data de início já passou. Use o horário de agora ou um momento futuro."
    if data_fim is None:
        erros["fim"] = "Informe a data e a hora do fim previsto."
    elif data_inicio is not None and data_fim <= data_inicio:
        erros["fim"] = "O fim previsto precisa ser depois do início."
    elif data_fim <= agora:
        erros["fim"] = "O fim previsto precisa estar no futuro."

    if erros:
        raise AnuncioInvalido(erros)

    dados, tipo = catalogo.imagem(carta.imagem)
    pasta_de_fotos.mkdir(parents=True, exist_ok=True)
    arquivo = pasta_de_fotos / f"{uuid4().hex}{EXTENSOES[tipo]}"
    arquivo.write_bytes(dados)
    try:
        with transacao(leiloes.conexao):
            nova = vendedor.cadastrarCarta(carta.nome, leiloes.jogo(carta.jogo), edicao, condicao, descricao,
                                           [PREFIXO_DAS_FOTOS + arquivo.name])
            # RN17: o leilão guarda o incremento e a taxa da loja como estão agora.
            leilao = vendedor.criarLeilao(nova, valor, data_inicio, data_fim, configuracao.incrementoMinimo,
                                          agora, configuracao.taxaPercentual)
            return leiloes.adicionar(leilao)
    except BaseException:
        arquivo.unlink(missing_ok=True)
        raise
