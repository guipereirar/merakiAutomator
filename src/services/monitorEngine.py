import os, json, time, logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from src.api.merakiClient import MerakiClient
from .notificationService import NotificationService

class MonitorEngine:
    def __init__(self):
        self.STATE_FILE = "estado.json"
        self.notifier = NotificationService()

    def carregarEstado(self):
        if os.path.exists(self.STATE_FILE):
            try:
                with open(self.STATE_FILE, 'r') as arquivo:
                    return json.load(arquivo)
            except json.JSONDecodeError:
                logging.error("Arquivo JSON corrompido ou vazio detectado. Iniciando estado limpo.")
                return {}
        return {}

    def salvarEstado(self, estado):
        temp_file = self.STATE_FILE + ".tmp"
        with open(temp_file, 'w') as arquivo:
            json.dump(estado, arquivo, indent=4)
        os.replace(temp_file, self.STATE_FILE)

    def limparFantasmas(self, estado, uplinksData):
        seriais_ativos = [device.get('serial') for device in uplinksData]
        chaves_remover = [chave for chave, dados in estado.items() if dados.get("serial") not in seriais_ativos]
        for chave in chaves_remover:
            del estado[chave]
            logging.info(f"Removendo loja inexistente do monitoramento: {chave}")

    def verificarLoja(self, device, lojasMap, client, estado):
        try:
            netId = device.get('networkId')
            if netId not in lojasMap: return

            nomeLoja = lojasMap[netId]
            serial = device.get('serial')
            uplinks = device.get('uplinks', [])

            for link in uplinks:
                interface = link['interface']
                status = link['status']
                motivoAlerta = None
                tipoAlerta = None

                if status == 'failed':
                    motivoAlerta = f'Problema logico na {interface}.'
                    tipoAlerta = "LOGICO"
                elif status == 'active':
                    historico = None
                    for tentativa in range(3):
                        try:
                            historico = client.getLatencyHistory(serial)
                            break
                        except Exception as e:
                            if tentativa < 2: time.sleep(2)
                            else: logging.error(f"[FALHA API] Esgotadas as 3 tentativas de latencia para {nomeLoja}: {e}")

                    if historico and len(historico) > 0:
                        latencia = historico[-1].get('latencyMs')
                        if latencia is not None and latencia > 60:
                            motivoAlerta = f"Alta latencia na {interface}: {latencia}ms"
                            tipoAlerta = "LATENCIA"

                chaveAlerta = f"{nomeLoja} | {interface} | {tipoAlerta}"
                agora = datetime.now()

                if motivoAlerta:
                    if chaveAlerta not in estado:
                        estado[chaveAlerta] = {
                            "inicio_falha": agora.isoformat(),
                            "email_enviado": False,
                            "serial": serial
                        }
                        logging.warning(f"{nomeLoja} ({interface}) com erro. Aguardando persistencia de 30min.")
                    else:
                        inicio = datetime.fromisoformat(estado[chaveAlerta]["inicio_falha"])
                        tempo_decorrido = agora - inicio
                        if tempo_decorrido > timedelta(minutes=30) and not estado[chaveAlerta]["email_enviado"]:
                            self.notifier.enviarAlerta(nomeLoja, motivoAlerta, serial, tipoAlerta)
                            estado[chaveAlerta]["email_enviado"] = True
                else:
                    chaves_relacionadas = [c for c in estado if f"{nomeLoja} | {interface}" in c]
                    for c in chaves_relacionadas:
                        if not estado[c]["email_enviado"]:
                            del estado[c]
                            logging.info(f"{nomeLoja} ({interface}) estabilizou antes dos 30min. Removida da fila.")
                        else:
                            inicio = datetime.fromisoformat(estado[c]["inicio_falha"])
                            tempo_decorrido = agora - inicio
                            if tempo_decorrido > timedelta(hours=6):
                                del estado[c]
                                logging.info(f"{nomeLoja} ({interface}) cumpriu a carencia ({tempo_decorrido}) e foi LIMPA do estado.")
                            else:
                                logging.debug(f"{nomeLoja} ({interface}) esta OK, aguardando carencia de 6h. Passaram {tempo_decorrido}.")
        except Exception as e:
            logging.error(f"[ERRO CRITICO] Falha inesperada na loja {device.get('serial')}: {e}")

    def rodar_monitoramento(self):
        logging.info("Iniciando ciclo de monitoramento.")
        client = MerakiClient(os.getenv("API_KEY"), os.getenv("ORGANIZATION_ID"))
        estado = self.carregarEstado()

        networks = client.getNetworks()
        lojasMap = {n['id']: n['name'] for n in networks if 'loja' in n['name'].lower()}
        uplinksData = client.getUplinks()

        with ThreadPoolExecutor(max_workers=5) as executor:
            for device in uplinksData:
                executor.submit(self.verificarLoja, device, lojasMap, client, estado)
        
        self.limparFantasmas(estado, uplinksData)
        self.salvarEstado(estado)
        logging.info("Ciclo de monitoramento finalizado. Estado salvo.")