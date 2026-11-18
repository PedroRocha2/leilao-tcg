import smtplib
import ssl
from email.message import EmailMessage

from app.dominio.dinheiro import formatar_reais
from app.dominio.leiloes import Leilao

TEMPO_LIMITE = 10
PORTA_PADRAO = 587
PORTA_SSL = 465


class CorreioIndisponivel(Exception):
    pass


class CorreioLocal:
    """Sem SMTP configurado: não envia nada."""
    externo = False

    def enviar(self, destinatario: str, assunto: str, texto: str) -> None:
        return None


class CorreioSMTP:
    externo = True

    def __init__(self, servidor: str, porta: int = PORTA_PADRAO, usuario: str = "", senha: str = "",
                 remetente: str = ""):
        self._servidor, self._porta = servidor, porta
        self._usuario, self._senha = usuario, senha
        self._remetente = remetente or usuario
        if not self._remetente:
            raise ValueError("O e-mail precisa de um remetente: informe o remetente ou o usuário do servidor.")

    def enviar(self, destinatario: str, assunto: str, texto: str) -> None:
        try:
            mensagem = EmailMessage()
            mensagem["From"] = self._remetente
            mensagem["To"] = destinatario
            # Sem quebras de linha, o nome da carta não injeta cabeçalhos.
            mensagem["Subject"] = " ".join(assunto.split())
            mensagem.set_content(texto)
            with self._conectar() as smtp:
                if self._usuario:
                    smtp.login(self._usuario, self._senha)
                smtp.send_message(mensagem)
        except (OSError, smtplib.SMTPException, ValueError) as erro:
            raise CorreioIndisponivel(f"o servidor de e-mail {self._servidor} não enviou a mensagem: {erro}") from erro

    def _conectar(self):
        contexto = ssl.create_default_context()
        if self._porta == PORTA_SSL:
            return smtplib.SMTP_SSL(self._servidor, self._porta, timeout=TEMPO_LIMITE, context=contexto)
        smtp = smtplib.SMTP(self._servidor, self._porta, timeout=TEMPO_LIMITE)
        try:
            smtp.ehlo()
            if smtp.has_extn("starttls"):
                smtp.starttls(context=contexto)
                smtp.ehlo()
            elif self._usuario:
                # Sem TLS, a senha passaria aberta pela rede.
                raise smtplib.SMTPException("o servidor não oferece conexão cifrada (STARTTLS)")
        except BaseException:
            smtp.close()
            raise
        return smtp


def aviso_de_pagamento(leilao: Leilao, link: str | None = None) -> tuple[str, str]:
    """O código fica fora do assunto, que aparece nas notificações."""
    arremate, carta = leilao.transacao, leilao.carta
    linhas = [
        f"Olá, {arremate.comprador.nome}.",
        "",
        f"Recebemos o pagamento de {formatar_reais(arremate.valor)} pelo arremate de {carta.nome}, {carta.edicao}.",
        "",
        f"Código de retirada: {arremate.codigoRetirada}",
        "",
        "Apresente este código no balcão da loja para retirar a carta. Não o compartilhe: é ele que a loja "
        "confere na entrega.",
    ]
    if link:
        linhas += ["", f"O código também fica em Minha Conta > Arremates: {link}"]
    linhas += ["", "Leilão TCG"]
    return f"Pagamento confirmado: {carta.nome}", "\n".join(linhas)
