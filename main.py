from src.api.merakiClient import MerakiClient
import os, json, time
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

load_dotenv()

STATE_FILE = "monitor_estado.json"

def carregarEstado():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as arquivo:
            return json.load(arquivo)
    return {}

def salvarEstado(estado):
    with open(STATE_FILE, 'w') as arquivo:
        json.dump(estado, arquivo, indent=4)

def alertaEmail(loja, motivo, serial, tipoAlerta):
    print(f"✉️ [ENVIANDO EMAIL] {tipoAlerta} | {loja} | MOTIVO: {motivo}")

def verificarLoja(device, lojasMap, client, estado):
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

        # 1. Identificação do Problema
        if status == 'not connected':
            motivoAlerta = f'Problema físico na {interface}.'
            tipoAlerta = "FISICO"
        elif status == 'failed':
            motivoAlerta = f'Problema lógico na {interface}.'
            tipoAlerta = "LOGICO"
        elif status == 'active':
            try:
                # Verificação de latência opcional (pode ser lenta, cuidado)
                historico = client.getLatencyHistory(serial)
                if historico and historico[-1].get('latencyMs', 0) > 60:
                    latencia = historico[-1]['latencyMs']
                    motivoAlerta = f"Alta latência na {interface}: {latencia}ms"
                    tipoAlerta = "LATENCIA"
            except: pass

        chaveAlerta = f"{nomeLoja} | {interface} | {tipoAlerta}"
        agora = datetime.now()

        # 2. Lógica de Alerta e Persistência
        if motivoAlerta:
            if chaveAlerta not in estado:
                # Primeira vez que o erro aparece: anota o horário mas NÃO manda e-mail
                estado[chaveAlerta] = {
                    "inicio_falha": agora.isoformat(),
                    "email_enviado": False,
                    "serial": serial
                }
                print(f"{nomeLoja} ({interface}) detectada com erro. Aguardando persistência de 30min.")
            else:
                # O erro já existia. Vamos ver há quanto tempo.
                inicio = datetime.fromisoformat(estado[chaveAlerta]["inicio_falha"])
                tempo_decorrido = agora - inicio

                if tempo_decorrido > timedelta(minutes=30) and not estado[chaveAlerta]["email_enviado"]:
                    alertaEmail(nomeLoja, motivoAlerta, serial, tipoAlerta)
                    estado[chaveAlerta]["email_enviado"] = True
        
        # 3. Lógica de Limpeza (Se o link está OK)
        else:
            # Encontra se essa loja/interface está no nosso "caderninho" de problemas
            chaves_relacionadas = [c for c in estado if f"{nomeLoja} | {interface}" in c]
            
            for c in chaves_relacionadas:
                # CENÁRIO A: Voltou a ficar ACTIVE rápido (antes de 30 min / não mandou email)
                if not estado[c]["email_enviado"]:
                    del estado[c]
                    print(f"{nomeLoja} ({interface}) estabilizou antes dos 30min. Removida da fila de alertas.")
                
                # CENÁRIO B: Já tinha ficado fora > 30 min e já mandou email. (Aplica carência de 6h)
                else:
                    inicio = datetime.fromisoformat(estado[c]["inicio_falha"])
                    if agora - inicio > timedelta(hours=6):
                        del estado[c]
                        print(f"{nomeLoja} ({interface}) cumpriu as 6h de carência e foi limpa do registro.")

def rodar_monitoramento():
    print(f"\nIniciando ciclo de monitoramento: {datetime.now().strftime('%H:%M:%S')}")
    client = MerakiClient(os.getenv("API_KEY"), os.getenv("ORGANIZATION_ID"))
    estado = carregarEstado()

    networks = client.getNetworks()
    lojasMap = {n['id']: n['name'] for n in networks if 'loja' in n['name'].lower()}
    uplinksData = client.getUplinks()

    # Como não usamos mais o time.sleep(120) dentro da thread, 10 workers são suficientes
    with ThreadPoolExecutor(max_workers=10) as executor:
        for device in uplinksData:
            executor.submit(verificarLoja, device, lojasMap, client, estado)
    
    salvarEstado(estado)

if __name__ == "__main__":
    while True:
        try:
            rodar_monitoramento()
        except Exception as e:
            print(f"Erro crítico no loop: {e}")
        
        print("Aguardando 5 minutos para a próxima verificação...")
        time.sleep(300) # 300 segundos = 5 minutos