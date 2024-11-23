# -*- coding: utf-8 -*-
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

            logger.info(f"Fecha del correo: {email_date}, "
                        f"Hora actual: {current_time}, "
                        f"Diferencia: {time_difference.total_seconds()} segundos")

            return is_valid, email_date

        except Exception as e:
            logger.error(f"Error al procesar fecha: {str(e)}")
            return False, None

    async def check_email_for_codes(self, email_address: str) -> dict:
        try:
            # Validar formato de correo básico
            if not re.match(r"[^@]+@[^@]+\.[^@]+", email_address):
                logger.warning(f"Formato de correo inválido: {email_address}")
                return {
                    "has_code": False,
                    "status": "error",
                    "message": "El formato del correo electrónico no es válido",
                    "email": email_address,
                    "timestamp": datetime.now().isoformat()
                }

            email_address = email_address.lower()
            logger.info(f"Buscando códigos para el correo: {email_address}")

            mail = self._get_mail_connection()
            mail.select("INBOX")

            # Buscar correos con criterios más flexibles
            date = (datetime.now() - timedelta(minutes=20)).strftime("%d-%b-%Y")
            search_criteria = (
                f'(SINCE "{date}" FROM "info@account.netflix.com")'
            ).encode('utf-8')

            logger.info(f"Criterios de búsqueda: {search_criteria}")

            _, messages = mail.search(None, search_criteria)
            if not messages[0]:
                logger.info(f"No se encontraron correos para {email_address}")
                return {
                    "has_code": False,
                    "status": "warning",
                    "message": "No se encontraron correos de Netflix asociados a esta cuenta",
                    "email": email_address,
                    "timestamp": datetime.now().isoformat()
                }

            message_nums = messages[0].split()
            message_nums.reverse()
            logger.info(f"Correos encontrados: {len(message_nums)}")

            expired_codes_found = False
            invalid_recipient_found = False

            for num in message_nums[:50]:  # Revisamos los últimos 50 correos
                try:
                    _, msg_data = mail.fetch(num, "(RFC822)")
                    email_message = email.message_from_bytes(msg_data[0][1])

                    # Verificar destinatario y asunto
                    to_address = email_message.get('To', '').lower()
                    subject = email_message.get('Subject', '').lower()

                    logger.info(
                        f"Procesando correo - Para: {to_address}, Asunto: {subject}")

                    if email_address not in to_address:
                        invalid_recipient_found = True
                        logger.info(
                            f"Correo no coincide con destinatario: {to_address}")
                        continue

                    if "codigo de acceso temporal" not in subject:
                        logger.info(f"Asunto no coincide: {subject}")
                        continue

                    # Verificar tiempo válido
                    is_valid, email_date = self._is_email_valid(email_message)
                    if not is_valid:
                        expired_codes_found = True
                        logger.info(f"Correo expirado para {email_address}")
                        continue

                    # Procesar cuerpo del correo
                    body = self._get_email_body(email_message)
                    if not body:
                        logger.info("Cuerpo del correo vacío")
                        continue

                    soup = BeautifulSoup(body, 'lxml', from_encoding='utf-8')

                    # Buscar el botón con múltiples estrategias
                    get_code_button = None

                    # 1. Buscar por texto exacto
                    get_code_button = soup.find('a', string='Obtener código')
                    if not get_code_button:
                        # 2. Buscar por texto case-insensitive
                        get_code_button = soup.find(
                            'a', string=lambda x: x and 'obtener código' in x.lower())
                    if not get_code_button:
                        # 3. Buscar por estilo de Netflix
                        get_code_button = soup.find(
                            'a', style=lambda x: x and '#e50914' in x)
                    if not get_code_button:
                        # 4. Buscar cualquier enlace que contenga netflix y código
                        get_code_button = soup.find(
                            'a', href=lambda x: x and 'netflix.com' in x.lower() and 'codigo' in x.lower())

                    # Corregir esta línea
                    logger.info(f"Botón encontrado: {get_code_button is not None}")

                    if get_code_button and (code_url := get_code_button.get('href')):
                        if 'netflix.com' in code_url:
                            logger.info(
                                f"URL del código encontrada: {code_url}")

                            message_guid = re.search(
                                r'messageGuid=([^&]+)', code_url)
                            remaining_seconds = 900 - \
                                (datetime.now(email_date.tzinfo) -
                                 email_date).total_seconds()
                            remaining_minutes = max(
                                1, int(remaining_seconds / 60))

                            return {
                                "has_code": True,
                                "status": "success",
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

            # Determinar el mensaje apropiado según el caso
            if expired_codes_found:
                return {
                    "has_code": False,
                    "status": "warning",
                    "message": "Se encontraron códigos pero ya han expirado. Solicite un nuevo código.",
                    "email": email_address,
                    "timestamp": datetime.now().isoformat()
                }
            elif invalid_recipient_found:
                return {
                    "has_code": False,
                    "status": "error",
                    "message": "El correo proporcionado no coincide con ningún destinatario",
                    "email": email_address,
                    "timestamp": datetime.now().isoformat()
                }

            return {
                "has_code": False,
                "status": "info",
                "message": "No se encontraron códigos válidos para este correo",
                "email": email_address,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error general: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "message": f"Error del servidor: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
            )
