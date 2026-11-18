from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.catalogo import EXTENSOES, CartaDoCatalogo, Catalogo
from app.db import transacao
from app.dominio.contas import Cliente
from app.dominio.dinheiro import ValorMonetarioInvalido, ler_reais
from app.dominio.financeiro import OperacaoRecusada
from app.dominio.leiloes import CONDICOES, Carta, Leilao, StatusCarta
from app.dominio.loja import ConfiguracaoLoja
from app.repositorios.leiloes import RepositorioLeiloes

PREFIXO_DAS_FOTOS = "fotos/"
TAMANHO_DA_DESCRICAO = 1000
MAXIMO_DE_FOTOS = 6
TAMANHO_MAXIMO_DA_FOTO = 8 * 1024 * 1024
# O sufixo do arquivo diz se a foto é do catálogo ou do vendedor.
_DO_CATALOGO, _DO_VENDEDOR = "-catalogo", "-vendedor"
# O formulário vem com o horário em que foi aberto: quem demora a enviar não é barrado.
TOLERANCIA_DO_INICIO = timedelta(minutes=15)


@dataclass
class AnuncioInvalido(Exception):
    erros: dict[str, str] = field(default_factory=dict)


def ler_data_hora(texto: str | None, fuso: ZoneInfo) -> datetime | None:
    try:
        return datetime.fromisoformat(texto or "").replace(tzinfo=fuso)
    except ValueError:
        return None


def tipo_da_imagem(dados: bytes) -> str | None:
    """Pelos primeiros bytes: o nome e o tipo enviados pelo navegador não são confiáveis."""
    if dados.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if dados.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if dados[:4] == b"RIFF" and dados[8:12] == b"WEBP":
        return "image/webp"
    return None


def foto_do_vendedor(foto: str) -> bool:
    return foto.startswith(PREFIXO_DAS_FOTOS) and foto.rsplit(".", 1)[0].endswith(_DO_VENDEDOR)


def _conferir_fotos(fotos: Sequence[bytes]) -> str | None:
    if len(fotos) > MAXIMO_DE_FOTOS:
        return f"Envie no máximo {MAXIMO_DE_FOTOS} fotos."
    megabytes = TAMANHO_MAXIMO_DA_FOTO // (1024 * 1024)
    for posicao, dados in enumerate(fotos, start=1):
        if len(dados) > TAMANHO_MAXIMO_DA_FOTO:
            return f"A foto {posicao} passa de {megabytes} MB. Envie uma foto menor."
        if tipo_da_imagem(dados) is None:
            return f"A foto {posicao} não é uma imagem JPEG, PNG ou WebP."
    return None


def anunciar_carta(leiloes: RepositorioLeiloes, catalogo: Catalogo, vendedor: Cliente, pasta_de_fotos: Path, *,
                   carta: CartaDoCatalogo, edicao: str, condicao: str, descricao: str, lance_inicial: str,
                   inicio: str, fim: str, agora: datetime, fuso: ZoneInfo,
                   configuracao: ConfiguracaoLoja, fotos: Sequence[bytes] = ()) -> Leilao:
    """RF03: cadastra a carta e cria o leilão, que nasce pendente (RN12)."""
    erros: dict[str, str] = {}

    erro_nas_fotos = _conferir_fotos(fotos)
    if erro_nas_fotos:
        erros["fotos"] = erro_nas_fotos

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
    # A imagem do catálogo vem primeiro: é a capa nas listas.
    imagens = [(dados, tipo, _DO_CATALOGO)] + [(foto, tipo_da_imagem(foto), _DO_VENDEDOR) for foto in fotos]
    arquivos: list[Path] = []
    try:
        for conteudo, formato, origem in imagens:
            arquivos.append(pasta_de_fotos / f"{uuid4().hex}{origem}{EXTENSOES[formato]}")
            arquivos[-1].write_bytes(conteudo)
        with transacao(leiloes.conexao):
            nova = vendedor.cadastrarCarta(carta.nome, leiloes.jogo(carta.jogo), edicao, condicao, descricao,
                                           [PREFIXO_DAS_FOTOS + arquivo.name for arquivo in arquivos],
                                           catalogo.atributos(carta.jogo, carta.especificacoes))
            # RN17: incremento e taxa ficam como estão agora.
            leilao = vendedor.criarLeilao(nova, valor, data_inicio, data_fim, configuracao.incrementoMinimo,
                                          agora, configuracao.taxaPercentual)
            return leiloes.adicionar(leilao)
    except BaseException:
        for arquivo in arquivos:
            arquivo.unlink(missing_ok=True)
        raise


def cancelar_leilao(leiloes: RepositorioLeiloes, vendedor: Cliente, numero: int, agora: datetime) -> Leilao | None:
    """RF20: cancela o leilão sem lances; None se não existe ou é de outro vendedor."""
    with transacao(leiloes.conexao, imediata=True):
        # Relê com o banco travado: um lance pode ter chegado nesse meio-tempo.
        leilao = leiloes.por_id(numero)
        if leilao is None or not leilao.carta.vendedor.ehOMesmo(vendedor):
            return None
        try:
            leilao.cancelar(agora)
        except ValueError as erro:
            raise OperacaoRecusada(str(erro)) from erro
        leiloes.salvar_status(leilao)
    return leilao


def apagar_fotos(carta: Carta, pasta_de_fotos: Path) -> None:
    """As fotos da carga inicial são arquivos do site e ficam."""
    for foto in carta.fotos:
        if foto.startswith(PREFIXO_DAS_FOTOS):
            (pasta_de_fotos / foto.removeprefix(PREFIXO_DAS_FOTOS)).unlink(missing_ok=True)


def pode_excluir(leilao: Leilao) -> bool:
    """RF25: só o leilão que o próprio vendedor cancelou."""
    return leilao.carta.status == StatusCarta.CANCELADA and not leilao.lances and leilao.transacao is None


def excluir_leilao(leiloes: RepositorioLeiloes, vendedor: Cliente, numero: int,
                   pasta_de_fotos: Path) -> Leilao | None:
    """RF25: apaga carta, fotos e leilão; None se não existe ou é de outro vendedor."""
    with transacao(leiloes.conexao, imediata=True):
        leilao = leiloes.por_id(numero)
        if leilao is None or not leilao.carta.vendedor.ehOMesmo(vendedor):
            return None
        if not pode_excluir(leilao):
            raise OperacaoRecusada("Só dá para excluir um leilão que você cancelou.")
        leiloes.remover(leilao)
    # Só depois do commit: se a exclusão falhar, as fotos continuam.
    apagar_fotos(leilao.carta, pasta_de_fotos)
    return leilao
