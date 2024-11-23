from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from fastapi import HTTPException
import logging
import imaplib
import email
import re
import socket
from email.header import decode_header
from email.utils import parsedate_to_datetime
from os import getenv
from src.services.code_extractor import CodeExtractor

logger = logging.getLogger(__name__)


class EmailCodeService:
    def __init__(self, db: Session):
        self.db = db
        self.code_extractor = CodeExtractor()

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

    def _get_mail_connection(self):
        """Reutiliza la conexión IMAP si está activa"""
        current_time = datetime.now()

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
            current_time = datetime.now(email_date.tzinfo)

            # Verificar si el correo tiene menos de 15 minutos
            time_difference = current_time - email_date
            is_valid = time_difference.total_seconds() < 900  # 15 minutos

            logger.info(f"Validación de correo - Fecha: {email_date}, Hora actual: {
                        current_time}, Diferencia: {time_difference.total_seconds()}s, Válido: {is_valid}")

            return is_valid, email_date

        except Exception as e:
            logger.error(f"Error al procesar fecha: {str(e)}")
            return False, None


    async def check_email_for_codes(self, email_address: str) -> dict:
        try:
            email_address = email_address.lower()
            mail = self._get_mail_connection()
            mail.select("INBOX")

            # Calcular el rango de tiempo para la búsqueda
            current_time = datetime.now()
            start_time = current_time - timedelta(minutes=20)   

            # Manejar el cambio de día
            if start_time.date() != current_time.date():
                date_criteria = f'(OR SINCE "{start_time.strftime("%d-%b-%Y")}" SINCE "{current_time.strftime("%d-%b-%Y")}")'.encode()
            else:
                date_criteria = f'SINCE "{start_time.strftime("%d-%b-%Y")}"'.encode()

                # Criterios de búsqueda actualizados
            search_criteria = [
                date_criteria,
                b'FROM', b'info@account.netflix.com',
                b'SUBJECT', b'Tu codigo de acceso temporal de Netflix'
            ]

            logger.info(f"Búsqueda - Hora actual: {current_time}, Inicio: {start_time}, Criterios: {search_criteria}")

            _, messages = mail.search(None, *search_criteria)
            if not messages[0]:
                return {
                    "has_code": False,
                    "message": "No se encontraron códigos pendientes",
                    "email": email_address,
                    "timestamp": datetime.now().isoformat()
                }

            # Procesar correos del más reciente al más antiguo
            message_nums = messages[0].split()
            message_nums.reverse()

            for num in message_nums[:80]:  # Limitar a los 80 más recientes
                try:
                    _, msg_data = mail.fetch(num, "(RFC822)")
                    email_message = email.message_from_bytes(msg_data[0][1])

                    # Verificar destinatario
                    to_address = email_message.get('To', '').lower()
                    if email_address not in to_address:
                        continue

                    # Verificar tiempo válido
                    is_valid, email_date = self._is_email_valid(email_message)
                    if not is_valid:
                        logger.info(f"Correo expirado para {email_address}")
                        continue

                    # Procesar cuerpo del correo
                    body = self._get_email_body(email_message)
                    if not body:
                        continue

                    soup = BeautifulSoup(body, 'lxml', from_encoding='utf-8')

                    # Buscar botón de código de forma optimizada
                    get_code_button = (
                        soup.find('a', class_='btn-get-code') or
                        soup.find('a', string=lambda x: x and any(phrase in x.lower() for phrase in [
                            'obtener codigo', 'get code', 'obtener tu codigo'
                        ])) or
                        soup.find('a', style=lambda x: x and '#e50914' in x)
                    )

                    if get_code_button and (code_url := get_code_button.get('href')):
                        if 'netflix.com' in code_url:
                            message_guid = re.search(
                                r'messageGuid=([^&]+)', code_url)

                            # Calcular tiempo restante
                            remaining_seconds = 980 - \
                                (datetime.now(email_date.tzinfo) -
                                 email_date).total_seconds()
                            remaining_minutes = max(
                                1, int(remaining_seconds / 60))

                            return {
                                "has_code": True,
                                "code_url": code_url,
                                "email": email_address,
                                "type": "netflix_code",
                                "message": "Código válido encontrado",
                                "message_guid": message_guid.group(1) if message_guid else None,
                                "expires_in": f"{remaining_minutes} minutos",
                                "email_date": email_date.isoformat(),
                                "timestamp": datetime.now().isoformat()
                            }
                except Exception as e:
                    logger.error(
                        f"Error procesando mensaje individual: {str(e)}")
                    continue

            return {
                "has_code": False,
                "message": "No se encontraron códigos válidos",
                "email": email_address,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error general: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            )
