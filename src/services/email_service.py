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
            raise HTTPException(status_code=503, detail="Timeout al conectar con el servidor de correo")
        except Exception as e:
            logger.error(f"Error de conexión: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error al conectar con el servidor de correo: {str(e)}")

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
                    return email_match.group(0)
            return None
        except Exception as e:
            logger.error(f"Error extrayendo email destinatario: {str(e)}")
            return None

    async def check_email_for_codes(self, email_address: str) -> dict:
        mail = None
        try:
            # Conectar a Gmail
            mail = self._connect_to_imap()
            mail.select("INBOX")

            # Buscar correos en los últimos 20 minutos
            date = (datetime.now() - timedelta(minutes=20)).strftime("%d-%b-%Y %H:%M:%S")
            search_criteria = f'(FROM "info@account.netflix.com") SINCE "{date}"'
            
            _, messages = mail.search(None, search_criteria)
            
            for num in messages[0].split():
                _, msg_data = mail.fetch(num, "(RFC822)")
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                # Verificar si el correo está dirigido al email solicitado
                to_address = self._get_recipient_email(email_message)
                if to_address and to_address.lower() == email_address.lower():
                    body = self._get_email_body(email_message)
                    soup = BeautifulSoup(body, 'html.parser')
                    
                    # Buscar el botón "Obtener código"
                    get_code_button = soup.find(
                        'a', string=lambda text: text and ('Obtener código' in text or 'Get code' in text)
                    )
                    
                    if get_code_button:
                        code_url = get_code_button.get('href')
                        return {
                            "has_code": True,
                            "code_url": code_url,
                            "email": email_address,
                            "type": "netflix_code",
                            "message": "Código encontrado. Haz clic en el botón para obtenerlo."
                        }
                    
                    # Buscar el botón de confirmación para Hogar con Netflix
                    confirm_button = soup.find(
                        'a', string=lambda text: text and (
                            'Sí, la envié yo' in text or 'Yes, it was me' in text)
                    )
                    
                    if confirm_button:
                        link = confirm_button.get('href')
                        return {
                            "has_code": True,
                            "code_url": link,
                            "email": email_address,
                            "type": "netflix_home",
                            "message": "Solicitud de confirmación encontrada."
                        }
            
            return {
                "has_code": False,
                "message": "No se encontraron códigos pendientes",
                "email": email_address
            }

        except Exception as e:
            logger.error(f"❌ Error general: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            if mail:
                try:
                    mail.close()
                    mail.logout()
                except:
                    pass