from src.api.merakiClient import MerakiClient
import os, json, time
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

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
    print(f"ENVIAR EMAIL {tipoAlerta} | Loja: {loja} | Serial: {serial} | MOTIVO: {motivo}")

def verificarErro(client, serial, interface, tipoErro):
    time.sleep(300) 
    try:
        if tipoErro == "status":
            todosUplinks = client.getUplinks()
            for dev in todosUplinks:
                if dev.get('serial') == serial:
                    for up in dev.get('uplinks', []):
                        if up['interface'] == interface and up['status'] not in ['active', 'ready']:
                            return True
            return False
        elif tipoErro == "latencia":
            historico = client.getLatencyHistory(serial)
            if historico:
                latencia = historico[-1].get('latencyMs')
                return latencia is not None and latencia > 60
    except:
        return False
    return False

def verificarLoja(device, lojasMap, client, estado):
    netId = device.get('networkId')
    if netId not in lojasMap:
        return

    nomeLoja = lojasMap[netId]
    serial = device.get('serial')
    uplinks = device.get('uplinks', [])

    for link in uplinks:
        interface = link['interface']
        status = link['status']
        motivoAlerta = None
        tipoAlerta = None

        if status == 'active':
            try:
                historico = client.getLatencyHistory(serial)
                if historico:
                    ultimaMetrica = historico[-1]
                    latencia = ultimaMetrica.get('latencyMs')
                    if latencia is not None and latencia > 60:
                        motivoAlerta = f"Alta latência no link {interface}: {latencia}ms"
                        tipoAlerta = "LATENCIA"
            except Exception:
                continue 
        elif status == 'not connected':
            motivoAlerta = f'Detectado problema físico na {interface}. Status: {status.upper()}.'
            tipoAlerta = "FISICO"
        elif status == 'failed':
            motivoAlerta = f'Detectado problema lógico na {interface}. Status: {status.upper()}.'
            tipoAlerta = "LOGICO"

        if motivoAlerta:
            chaveAlerta = f"{nomeLoja}, {interface}, {tipoAlerta}"
            hoje = datetime.now().strftime("%Y-%m-%d")

            if estado.get(chaveAlerta) == hoje:
                continue

            tipoErroValidar = "latencia" if tipoAlerta == "LATENCIA" else "status"
            if verificarErro(client, serial, interface, tipoErroValidar):
                alertaEmail(nomeLoja, motivoAlerta, serial, tipoAlerta)
                estado[chaveAlerta] = hoje

def main():
    client = MerakiClient(os.getenv("API_KEY"), os.getenv("ORGANIZATION_ID"))
    estado = carregarEstado()

    networks = client.getNetworks()
    lojasMap = {n['id']: n['name'] for n in networks if 'loja' in n['name'].lower()}
    
    uplinksData = client.getUplinks()

    with ThreadPoolExecutor(max_workers=20) as executor:
        for device in uplinksData:
            executor.submit(verificarLoja, device, lojasMap, client, estado)
    
    salvarEstado(estado)
    print("Ciclo de verificação finalizado e estado salvo.")

if __name__ == "__main__":
    main()