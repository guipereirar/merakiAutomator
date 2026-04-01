import os, time, logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("monitor.log", mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

from src.services.monitorEngine import MonitorEngine

if __name__ == "__main__":
    engine = MonitorEngine()
    try:
        while True:
            try:
                engine.rodar_monitoramento()
            except Exception as e:
                logging.error(f"[ERRO LOOP] Falha no ciclo principal: {e}")
            
            logging.info("Aguardando 5 minutos para a proxima verificacao...")
            time.sleep(300)
    except KeyboardInterrupt:
        logging.info("Monitoramento interrompido pelo usuario. Encerrando com seguranca...")