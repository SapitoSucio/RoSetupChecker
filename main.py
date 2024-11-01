import asyncio
import aiohttp
import datetime
import os
import logging
from aiohttp import ClientTimeout

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ROSetupChecker:
    def __init__(self):
        self.current_date = datetime.datetime.today()
        self.webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
        
        self.max_retries = 3
        self.retry_delay = 5
        self.request_timeout = ClientTimeout(total=5)
        
        self.urls = [
            ("http://rofull.gnjoy.com/ZERO_SETUP_{date_str}.exe", "%y%m%d", "kROZ_"),
            ("http://rofull.gnjoy.com/RagnarokZero_{date_str}.zip", "%y%m%d", "kROZ_"),
            ("http://rofull.gnjoy.com/RAG_SETUP_{date_str}.exe", "%y%m%d", "kRO_"),
            ("http://rofull.gnjoy.com/Ragnarok_{date_str}.zip", "%y%m%d", "kRO_"),
            ("http://twcdn.gnjoy.com.tw/ragnarok/Client/RAGNAROK_{date_str}.exe", "%Y%m%d", "twRO_"),
            ("http://twcdn.gnjoy.com.tw/ragnarok/Client/RO_Install_{date_str}.exe", "%y%m%d", "twRO_"),
            ("https://d364v3f2sbnp2e.cloudfront.net/RO_GGH_{date_str}.exe", "%Y-%m-%d", "RO_GGH_"),
        ]
        
        self.discord_message_template = """## Nuevo Official RO Setup:
**🔸Nombre:** {filename}
**🔸Tamaño:** {size} GB
**🔸Link:** {url}
"""

    async def check_url(self, session, url, date_str, prefix):
        for retry in range(self.max_retries):
            try:
                async with session.head(url, timeout=self.request_timeout) as response:
                    if response.status == 200:
                        logging.info(f"Archivo encontrado: {url}")
                        return url, date_str, prefix, response.headers.get('content-length', '0')
                    return None
            except aiohttp.ClientError as e:
                logging.error(f"Error al realizar la solicitud a {url}: {e}")
                if retry < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    logging.error(f"Se alcanzó el número máximo de reintentos para {url}")
                    return None

    async def process_date(self, date):
        logging.info(f"Procesando fecha: {date.strftime('%Y-%m-%d')}")
        async with aiohttp.ClientSession() as session:
            tasks = []
            for url_template, date_format, prefix in self.urls:
                date_str = date.strftime(date_format)
                url = url_template.format(date_str=date_str)
                tasks.append(self.check_url(session, url, date_str, prefix))
            
            results = await asyncio.gather(*tasks)
            valid_results = [r for r in results if r]
            
            for url, date_str, prefix, content_length in valid_results:
                filename = f"{prefix}{os.path.basename(url)}"
                total_size_in_gb = round(int(content_length) / (1024 ** 3), 2)
                
                discord_message = self.discord_message_template.format(
                    filename=filename, 
                    size=total_size_in_gb, 
                    url=url
                )
                
                logging.info(f"Enviando mensaje a Discord para: {filename}")
                try:
                    async with session.post(self.webhook_url, json={"content": discord_message}):
                        pass
                except Exception as e:
                    logging.error(f"Error al enviar mensaje a Discord: {e}")

    async def run(self):
        if not self.webhook_url:
            raise ValueError("DISCORD_WEBHOOK_URL environment variable is not set")

        logging.info("Iniciando proceso de verificación")
        await self.process_date(self.current_date)
        logging.info("Proceso completado")

def main():
    checker = ROSetupChecker()
    asyncio.run(checker.run())

if __name__ == "__main__":
    main()