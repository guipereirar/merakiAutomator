import smtplib, os, logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

class NotificationService:
    def __init__(self):
        self.user = os.getenv("EMAIL_USER")
        self.password = os.getenv("EMAIL_PASS")
        self.dest = os.getenv("EMAIL_DESTINO")
        self.server = os.getenv("SMTP_SERVER")
        self.port = int(os.getenv("SMTP_PORT", 587))

    def enviarAlerta(self, loja, motivo, serial, tipoAlerta):
        if not self.user:
            logging.info(f"[ENVIANDO EMAIL - SIMULADO] {tipoAlerta} | {loja} | MOTIVO: {motivo}")
            return

        msg = MIMEMultipart()
        msg["From"] = f"Monitoramento Meraki <{self.user}>"
        msg["To"] = self.dest
        msg["Subject"] = f"ALERTA {tipoAlerta}: {loja}"

        corpo = f"""
        Alerta de Monitoramento Meraki
        ----------------------------------------------
        Loja: {loja}
        Serial: {serial}
        Tipo: {tipoAlerta}
        Motivo: {motivo}
        Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
        ----------------------------------------------
        """
        msg.attach(MIMEText(corpo, "plain"))

        try:
            with smtplib.SMTP(self.server, self.port) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.sendmail(self.user, self.dest, msg.as_string())
            logging.info(f"[EMAIL ENVIADO] Sucesso ao notificar {tipoAlerta} da {loja}")
        except Exception as e:
            logging.error(f"[FALHA EMAIL] Erro ao enviar para {loja}: {e}")