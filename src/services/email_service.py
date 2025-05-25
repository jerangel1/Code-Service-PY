from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from fastapi import HTTPException
import logging
import imaplib
import email
import re
import socket
import pytz
from email.header import decode_header
from email.utils import parsedate_to_datetime
from os import getenv
from src.services.code_extractor import CodeExtractor

logger = logging.getLogger(__name__)

class EmailCodeService:
    def __init__(self, db: Session):
        self.db = db
        self.code_extractor = CodeExtractor()
        self.timezone = pytz.timezone('America/Caracas')

        # Configuración para Gmail central
        self.central_email = "serviciosnetplus@gmail.com"
        self.imap_server = "imap.gmail.com"
        self.imap_port = 993
        self.timeout = 60

        # Cache de conexión IMAP
        self._mail_connection = None
        self._last_connection_time = None
        self._connection_timeout = 300  # 5 minutos

        self.central_password = getenv('GMAIL_APP_PASSWORD')
        if not self.central_password:
            raise Exception("GMAIL_APP_PASSWORD no está configurado en .env")

    def _get_current_time(self):
        """Obtiene la hora actual en la zona horaria de Caracas"""
        return datetime.now(self.timezone)

    def _get_mail_connection(self):
        """Reutiliza la conexión IMAP si está activa"""
        current_time = self._get_current_time()

        if (self._mail_connection and self._last_connection_time and
                (current_time - self._last_connection_time).seconds < self._connection_timeout):
            try:
                self._mail_connection.noop()
                return self._mail_connection
            except:
                pass

        if self._mail_connection:
            try:
                self._mail_connection.close()
                self._mail_connection.logout()
            except:
                pass

        self._mail_connection = self._connect_to_imap()
        self._last_connection_time = current_time
        return self._mail_connection

    def _connect_to_imap(self):
        """Establece conexión con el servidor IMAP"""
        try:
            logger.info(f"Conectando a {self.imap_server}:{self.imap_port}")
            socket.setdefaulttimeout(self.timeout)
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.central_email, self.central_password)
            return mail
        except Exception as e:
            logger.error(f"Error de conexión: {str(e)}")
            raise HTTPException(
                status_code=503,
                detail={"status": "error",
                        "message": f"Error de conexión: {str(e)}"}
            )

    def _get_email_body(self, email_message) -> str:
        """Extrae el cuerpo del mensaje de correo"""
        try:
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/html":
                        payload = part.get_payload(decode=True)
                        return payload.decode('utf-8', errors='ignore')
            else:
                payload = email_message.get_payload(decode=True)
                return payload.decode('utf-8', errors='ignore')
        except Exception as e:
            logger.error(f"Error decodificando el cuerpo del email: {str(e)}")
            return ""

    def _is_email_valid(self, email_message) -> tuple[bool, datetime]:
        """Verifica si el correo está dentro del tiempo válido"""
        try:
            date_str = email_message.get('Date')
            if not date_str:
                return False, None

            email_date = parsedate_to_datetime(date_str)
            if email_date.tzinfo is None:
                email_date = self.timezone.localize(email_date)
            current_time = self._get_current_time()

            # Verificar si el correo tiene menos de 15 minutos
            time_difference = current_time - email_date
            is_valid = time_difference.total_seconds() < 900  # 15 minutos

            logger.info(f"Validación de correo - Fecha: {email_date}, Hora actual: {current_time}, Diferencia: {time_difference.total_seconds()}s, Válido: {is_valid}")
            return is_valid, email_date

        except Exception as e:
            logger.error(f"Error al procesar fecha: {str(e)}")
            return False, None

    async def check_email_for_codes(self, email_address: str) -> dict:
        try:
            email_address = email_address.lower()
            logger.info(f"Buscando códigos para: {email_address}")
            
            mail = self._get_mail_connection()
            mail.select("INBOX")

            # Calcular el rango de tiempo para la búsqueda
            current_time = self._get_current_time()
            start_time = current_time - timedelta(minutes=20)   

            # Búsqueda simplificada
            search_date = start_time.strftime("%d-%b-%Y")
            search_criteria = f'(SINCE "{search_date}" FROM "info@account.netflix.com")'.encode()

            # Agregar búsqueda para "Cómo actualizar tu hogar con Netflix"
            search_criteria_update = f'(SINCE "{search_date}" FROM "info@account.netflix.com" SUBJECT "Cómo actualizar tu hogar con Netflix")'.encode()

            logger.info(f"Búsqueda - Hora actual: {current_time}, Inicio: {start_time}, Criterios: {search_criteria}")

            _, messages = mail.search(None, search_criteria)
            logger.info(f"Mensajes encontrados: {len(messages[0].split()) if messages[0] else 0}")

            if not messages[0]:
                return {
                    "has_code": False,
                    "message": "No se encontraron códigos pendientes",
                    "email": email_address,
                    "timestamp": self._get_current_time().isoformat()
                }

            # Procesar correos del más reciente al más antiguo
            message_nums = messages[0].split()
            message_nums.reverse()

            for num in message_nums[:80]:
                try:
                    _, msg_data = mail.fetch(num, "(RFC822)")
                    email_message = email.message_from_bytes(msg_data[0][1])

                    # Verificar destinatario
                    to_address = email_message.get('To', '').lower()
                    logger.info(f"Verificando destinatario - To: {to_address}, Buscando: {email_address}")
                    
                    if email_address not in to_address:
                        continue

                    # Verificar tiempo válido
                    is_valid, email_date = self._is_email_valid(email_message)
                    if not is_valid:
                        logger.info(f"Correo expirado para {email_address}")
                        continue
                        
                    # Agregar atributo para rastrear el tipo de código
                    email_message.code_type = "netflix_code"

                    # Procesar cuerpo del correo
                    body = self._get_email_body(email_message)
                    if not body:
                        logger.info("Cuerpo del correo vacío")
                        continue

                    soup = BeautifulSoup(body, 'lxml', from_encoding='utf-8')
                    logger.info("Buscando botón de código...")

                    # Buscar botón de código
                    get_code_button = None
                    for link in soup.find_all('a'):
                        href = link.get('href', '')
                        text = link.get_text().lower()
                        style = link.get('style', '')
                        
                        logger.info(f"Enlace encontrado - Texto: {text}, Href: {href}, Style: {style}")
                        
                        if ('netflix.com' in href and 
                            ('codigo' in text or 'code' in text or 
                             'obtener' in text or 'get' in text or 
                             '#e50914' in style)):
                            get_code_button = link
                            break

                        # Nueva condición para el caso de "Cómo actualizar tu hogar con Netflix"
                        if ('netflix.com' in href and 
                            ('actualizar' in text or 'update' in text)):
                            get_code_button = link
                            break
                            
                        # Condición para detectar el botón "Sí, la envié yo" en emails de actualización de hogar
                        if ('netflix.com' in href and
                            ('sí, la envié yo' in text.lower() or 'si, la envie yo' in text.lower())):
                            logger.info(f"Botón de confirmación de actualización de hogar encontrado: {text}")
                            get_code_button = link
                            # Marcar como tipo de código de hogar
                            email_message.code_type = "netflix_home_update"
                            break

                    if get_code_button and (code_url := get_code_button.get('href')):
                        logger.info(f"URL del código encontrada: {code_url}")
                        
                        if 'netflix.com' in code_url:
                            message_guid = re.search(r'messageGuid=([^&]+)', code_url)

                            # Calcular tiempo restante
                            remaining_seconds = 900 - (self._get_current_time() - email_date).total_seconds()
                            remaining_minutes = max(1, int(remaining_seconds / 60))

                            code_type = getattr(email_message, 'code_type', "netflix_code")
                            message_text = "Código válido encontrado"
                            if code_type == "netflix_home_update":
                                message_text = "Confirmación de actualización de hogar encontrada"
                                
                            return {
                                "has_code": True,
                                "code_url": code_url,
                                "email": email_address,
                                "type": code_type,
                                "message": message_text,
                                "message_guid": message_guid.group(1) if message_guid else None,
                                "expires_in": f"{remaining_minutes} minutos",
                                "email_date": email_date.isoformat(),
                                "timestamp": self._get_current_time().isoformat()
                            }
                except Exception as e:
                    logger.error(f"Error procesando mensaje individual: {str(e)}")
                    continue

            return {
                "has_code": False,
                "message": "No se encontraron códigos válidos",
                "email": email_address,
                "timestamp": self._get_current_time().isoformat()
            }

        except Exception as e:
            logger.error(f"Error general: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "message": str(e),
                    "timestamp": self._get_current_time().isoformat()
                }
            )