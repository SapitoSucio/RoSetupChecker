import asyncio
import aiohttp
import datetime
import os
import logging
from aiohttp import ClientTimeout, ClientConnectorError, ServerTimeoutError, ClientError
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ROSetupChecker:
    def __init__(self):
        self.current_date = datetime.datetime.today()
        self.webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
        
        self.max_retries = 5
        self.retry_delay = 10
        self.request_timeout = ClientTimeout(total=30, connect=30)
        
        self.urls = [
            ("http://rofull.gnjoy.com/ZERO_SETUP_{date_str}.exe", "%y%m%d", "kROZ_"),
            ("http://rofull.gnjoy.com/RagnarokZero_{date_str}.zip", "%y%m%d", "kROZ_"),
            ("http://rofull.gnjoy.com/RAG_SETUP_{date_str}.exe", "%y%m%d", "kRO_"),
            ("http://rofull.gnjoy.com/Ragnarok_{date_str}.zip", "%y%m%d", "kRO_"),
            ("http://twcdn.gnjoy.com.tw/ragnarok/Client/RAGNAROK_{date_str}.exe", "%Y%m%d", "twRO_"),
            ("http://twcdn.gnjoy.com.tw/ragnarok/Client/RO_Install_{date_str}.exe", "%y%m%d", "twRO_"),
            ("https://d364v3f2sbnp2e.cloudfront.net/RO_GGH_{date_str}.exe", "%Y-%m-%d", "RO_GGH_"),
            ("https://ro1patch.gnjoylatam.com/LIVE/client/LATAM_SETUP_{date_str}.exe", "%y%m%d", "LATAM_"),
        ]
        
        self.discord_message_template = """## Nuevo Official RO Setup:
**🔸Nombre:** {filename}
**🔸Tamaño:** {size} GB
**🔸Link:** {url}
"""
        
        self.readme_header = """# RO Setup Checker 🐸

Este script verifica diariamente la disponibilidad de nuevos setups oficiales de Ragnarok Online para diferentes servidores (kRO, kROZ, twRO). Cuando encuentra uno nuevo, envía una notificación a un canal de Discord específico.

## Setups Encontrados 📦

"""
        self.readme_entry_template = "### {date}\n- [{filename}]({url}) ({size} GB)\n"

    async def check_url(self, session, url, date_str, prefix):
        for retry in range(self.max_retries):
            try:
                logging.info(f"Intentando request a {url} (intento {retry+1}/{self.max_retries})")
                async with session.head(url, timeout=self.request_timeout, allow_redirects=True) as response:
                    if response.status == 200:
                        logging.info(f"Archivo encontrado: {url}")
                        return url, date_str, prefix, response.headers.get('content-length', '0')
                    logging.info(f"URL no disponible: {url} - Código: {response.status}")
                    return None
            except asyncio.TimeoutError as e:
                logging.error(f"Timeout al conectar a {url}: {e}")
                if retry < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    logging.error(f"Se alcanzó el número máximo de reintentos por timeout para {url}")
                    return None
            except (ClientConnectorError, ServerTimeoutError) as e:
                logging.error(f"Error de conexión o timeout del servidor para {url}: {e}")
                if retry < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    logging.error(f"Se alcanzó el número máximo de reintentos por error de conexión para {url}")
                    return None
            except ClientError as e:
                logging.error(f"Error del cliente HTTP para {url}: {e}")
                if retry < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    logging.error(f"Se alcanzó el número máximo de reintentos por error de cliente para {url}")
                    return None
            except Exception as e:
                logging.error(f"Error inesperado al realizar la solicitud a {url}: {e}")
                if retry < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    logging.error(f"Se alcanzó el número máximo de reintentos para {url}")
                    return None

    def update_readme(self, new_entries):
        try:
            # Leer el README existente si existe
            readme_content = ""
            if os.path.exists("README.md"):
                with open("README.md", "r", encoding="utf-8") as f:
                    readme_content = f.read()

            # Extraer entradas existentes
            existing_entries = []
            if "## Setups Encontrados 📦" in readme_content:
                entries_section = readme_content.split("## Setups Encontrados 📦")[1].strip()
                existing_entries = re.findall(r"### .*?\n(?:- \[.*?\]\(.*?\).*?\n)+", entries_section, re.DOTALL)

            # Convertir entradas existentes a un formato estructurado
            parsed_entries = []
            for entry in existing_entries:
                date_match = re.search(r"### (.*?)\n", entry)
                if date_match:
                    date = date_match.group(1)
                    files = re.findall(r"- \[(.*?)\]\((.*?)\) \((.*?) GB\)", entry)
                    parsed_entries.append((date, files))

            # Agregar nuevas entradas
            current_date_str = self.current_date.strftime("%Y-%m-%d")
            new_files = []
            for url, date_str, prefix, content_length in new_entries:
                filename = f"{prefix}{os.path.basename(url)}"
                try:
                    size = round(int(content_length) / (1024 ** 3), 2)
                except (ValueError, TypeError):
                    logging.warning(f"Content-Length inválido para {url}: {content_length}")
                    size = 0
                new_files.append((filename, url, size))

            if new_files:
                parsed_entries.append((current_date_str, new_files))

            # Ordenar entradas por fecha (más reciente primero)
            parsed_entries.sort(key=lambda x: datetime.datetime.strptime(x[0], "%Y-%m-%d"), reverse=True)

            # Reconstruir el README
            new_readme = self.readme_header
            for date, files in parsed_entries:
                new_readme += f"### {date}\n"
                for filename, url, size in files:
                    new_readme += f"- [{filename}]({url}) ({size} GB)\n"
                new_readme += "\n"

            # Guardar el README actualizado
            with open("README.md", "w", encoding="utf-8") as f:
                f.write(new_readme)

            logging.info("README.md actualizado exitosamente")
        except Exception as e:
            logging.error(f"Error al actualizar README.md: {e}")

    async def process_date(self, date):
        logging.info(f"Procesando fecha: {date.strftime('%Y-%m-%d')}")
        conn = aiohttp.TCPConnector(limit=5, ssl=False)
        async with aiohttp.ClientSession(connector=conn) as session:
            tasks = []
            for url_template, date_format, prefix in self.urls:
                date_str = date.strftime(date_format)
                url = url_template.format(date_str=date_str)
                tasks.append(self.check_url(session, url, date_str, prefix))
            
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                valid_results = []
                for result in results:
                    if isinstance(result, Exception):
                        logging.error(f"Error en una de las tareas: {result}")
                    elif result:
                        valid_results.append(result)
                
                # Actualizar README con los nuevos resultados
                self.update_readme(valid_results)
                
                for url, date_str, prefix, content_length in valid_results:
                    filename = f"{prefix}{os.path.basename(url)}"
                    try:
                        total_size_in_gb = round(int(content_length) / (1024 ** 3), 2)
                    except (ValueError, TypeError):
                        logging.warning(f"Content-Length inválido para {url}: {content_length}")
                        total_size_in_gb = 0
                    
                    discord_message = self.discord_message_template.format(
                        filename=filename, 
                        size=total_size_in_gb, 
                        url=url
                    )
                    
                    logging.info(f"Enviando mensaje a Discord para: {filename}")
                    try:
                        async with session.post(self.webhook_url, json={"content": discord_message}, timeout=ClientTimeout(total=10)):
                            pass
                    except Exception as e:
                        logging.error(f"Error al enviar mensaje a Discord: {e}")
            except Exception as e:
                logging.error(f"Error durante el procesamiento de las tareas: {e}")

    async def run(self):
        if not self.webhook_url:
            logging.warning("DISCORD_WEBHOOK_URL no está configurado, se omitirán las notificaciones")
        
        logging.info("Iniciando proceso de verificación")
        try:
            await self.process_date(self.current_date)
            logging.info("Proceso completado")
        except Exception as e:
            logging.error(f"Error en el proceso principal: {e}")

def main():
    try:
        checker = ROSetupChecker()
        asyncio.run(checker.run())
    except Exception as e:
        logging.error(f"Error fatal en el script: {e}")

if __name__ == "__main__":
    main()
