from src.api.merakiClient import MerakiClient
import os
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
load_dotenv()

def verificarLoja(device, lojasMap, client):
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

        if status not in ['active', 'ready']:
            motivoAlerta = f"Link {interface} está {status.upper()}"
        elif status == 'active':
            try:
                historico = client.getLatencyHistory(serial)
                if historico:
                    ultimaMetrica = historico[-1]
                    latencia = ultimaMetrica.get('latencyMs')
                    if latencia is not None and latencia > 60:
                        motivoAlerta = f"Alta latência no link {interface}: {latencia}ms"
            except Exception as e:
                pass 

        if motivoAlerta:
            alertaEmail(nomeLoja, motivoAlerta)

def alertaEmail(loja, motivo):
    print(f"ENVIAR EMAIL SOBRE {loja}. MOTIVO: {motivo}")

def main():
    client = MerakiClient(os.getenv("API_KEY"), os.getenv("ORGANIZATION_ID"))

    networks = client.getNetworks()
    lojasMap = {n['id']: n['name'] for n in networks if 'loja' in n['name'].lower()}
    
    uplinksData = client.getUplinks()

    with ThreadPoolExecutor(max_workers=10) as executor:
        for device in uplinksData:
            executor.submit(verificarLoja, device, lojasMap, client)

if __name__ == "__main__":
    main()