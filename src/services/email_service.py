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
        
        self.central_password = getenv('GMAIL_APP_PASSWORD')
        if not self.central_password:
            raise Exception("GMAIL_APP_PASSWORD no está configurado en .env")

    def _connect_to_imap(self):
        """Establece conexión con el servidor IMAP con timeout"""
        try:
            logger.info(f"Intentando conectar a {self.imap_server}:{self.imap_port}")
            socket.setdefaulttimeout(self.timeout)
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            
            logger.info(f"Intentando login con {self.central_email}")
            mail.login(self.central_email, self.central_password)
            logger.info("Login exitoso")
            
            return mail
        except socket.timeout:
            logger.error("Timeout al conectar con Gmail")
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "error",
                    "message": "Timeout al conectar con el servidor de correo",
                    "timestamp": datetime.now().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Error de conexión: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "message": "Error al conectar con el servidor de correo",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            )

    def _get_email_body(self, email_message) -> str:
        """Extrae el cuerpo del mensaje de correo"""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/html":
                    return part.get_payload(decode=True).decode()
        else:
            return email_message.get_payload(decode=True).decode()

    def _get_recipient_email(self, email_message) -> str:
        """Extrae el email del destinatario"""
        try:
            if 'To' in email_message:
                to_header = decode_header(email_message['To'])[0][0]
                if isinstance(to_header, bytes):
                    to_header = to_header.decode()
                email_match = re.search(r'[\w\.-]+@[\w\.-]+', to_header)
                if email_match:
                    return email_match.group(0).lower()
            return None
        except Exception as e:
            logger.error(f"Error extrayendo email destinatario: {str(e)}")
            return None

    async def check_email_for_codes(self, email_address: str) -> dict:
        mail = None
        try:
            email_address = email_address.lower()
            
            mail = self._connect_to_imap()
            mail.select("INBOX")
            
            # Buscar correos en los últimos 20 minutos
            date = (datetime.now() - timedelta(minutes=20)).strftime("%d-%b-%Y")
            search_criteria = f'(SINCE "{date}" FROM "info@account.netflix.com")'
            
            logger.info(f"Buscando correos para {email_address} con criterios: {search_criteria}")
            
            try:
                _, messages = mail.search(None, search_criteria)
                
                if not messages[0]:
                    logger.info(f"No se encontraron mensajes para {email_address}")
                    return {
                        "has_code": False,
                        "message": "No se encontraron códigos pendientes",
                        "email": email_address,
                        "timestamp": datetime.now().isoformat()
                    }
                
                for num in messages[0].split():
                    _, msg_data = mail.fetch(num, "(RFC822)")
                    email_body = msg_data[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    to_address = self._get_recipient_email(email_message)
                    logger.info(f"Comparando {to_address} con {email_address}")
                    
                    if to_address and to_address == email_address:
                        body = self._get_email_body(email_message)
                        soup = BeautifulSoup(body, 'html.parser')
                        
                        # Buscar botón "Obtener código"
                        get_code_button = soup.find(
                            'a',
                            class_=lambda x: x and ('btn-get-code' in x.lower() or 'button' in x.lower()),
                            string=lambda text: text and any(phrase in text for phrase in [
                                'Obtener código',
                                'Get code',
                                'Obtener tu código'
                            ])
                        )
                        
                        if not get_code_button:
                            get_code_button = soup.find(
                                'a',
                                string=lambda text: text and any(phrase in text for phrase in [
                                    'Obtener código',
                                    'Get code',
                                    'Obtener tu código'
                                ])
                            )
                        
                        if not get_code_button:
                            get_code_button = soup.find(
                                'a',
                                style=lambda x: x and 'background-color: #e50914' in x.lower()
                            )
                        
                        if get_code_button:
                            code_url = get_code_button.get('href')
                            
                            if code_url and ('netflix.com/login' in code_url or 'netflix.com/account/travel/verify' in code_url):
                                logger.info(f"✅ URL de código encontrada: {code_url}")
                                
                                message_guid = None
                                if 'messageGuid' in code_url:
                                    guid_match = re.search(r'messageGuid=([^&]+)', code_url)
                                    if guid_match:
                                        message_guid = guid_match.group(1)
                                
                                return {
                                    "has_code": True,
                                    "code_url": code_url,
                                    "email": email_address,
                                    "type": "netflix_code",
                                    "message": "Código encontrado. Haz clic en el botón para obtenerlo.",
                                    "message_guid": message_guid,
                                    "expires_in": "15 minutos",
                                    "timestamp": datetime.now().isoformat()
                                }
                            else:
                                logger.warning(f"⚠️ URL no válida encontrada: {code_url}")
                
                return {
                    "has_code": False,
                    "message": "No se encontraron códigos pendientes",
                    "email": email_address,
                    "timestamp": datetime.now().isoformat()
                }
                
            except imaplib.IMAP4.error as e:
                logger.error(f"Error IMAP al buscar mensajes: {str(e)}")
                raise HTTPException(
                    status_code=500,
                    detail={
                        "status": "error",
                        "message": "Error al buscar mensajes",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
                )
                
        except Exception as e:
            logger.error(f"❌ Error general: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "status": "error",
                    "message": "Error al procesar la solicitud",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            )
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except:
                    pass