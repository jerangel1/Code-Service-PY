from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
import logging
import imaplib
import email
import re
import socket
from email.header import decode_header

from src.models.email_account import EmailAccount
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
        self.timeout = 30  # Timeout en segundos
        
        # Obtener contraseña de la DB
        self.central_password = self._get_central_email_password()
        
        # Dominios autorizados específicos
        self.authorized_domains = [
            'netorgft1124943.onmicrosoft.com',
            'nplus600.com',
            'serviciosnp.com',
            'smartservicesnp.com',
            'snp2022.xyz'
        ]

    def _connect_to_imap(self):
        """Establece conexión con el servidor IMAP con timeout"""
        try:
            socket.setdefaulttimeout(self.timeout)
            mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            mail.login(self.central_email, self.central_password)
            return mail
        except socket.timeout:
            logger.error("Timeout al conectar con Gmail")
            raise HTTPException(
                status_code=503,
                detail="Timeout al conectar con el servidor de correo"
            )
        except imaplib.IMAP4.error as e:
            logger.error(f"Error IMAP: {str(e)}")
            raise HTTPException(
                status_code=401,
                detail="Error de autenticación con Gmail"
            )
        except Exception as e:
            logger.error(f"Error de conexión: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Error al conectar con el servidor de correo"
            )

    def _get_central_email_password(self) -> str:
        """Obtiene la contraseña del correo central desde la DB"""
        email_account = self.db.query(EmailAccount).filter(
            func.lower(EmailAccount.email) == self.central_email.lower()
        ).first()
        if not email_account:
            raise Exception("Correo central no configurado en la base de datos")
        return email_account.password

    async def check_email_for_codes(self, email_address: str) -> dict:
        mail = None
        try:
            # Validar dominio del correo
            domain = email_address.split('@')[1].lower()
            if domain not in self.authorized_domains:
                return self._handle_unauthorized_domain(domain)

            # Conectar a Gmail usando el nuevo método
            mail = self._connect_to_imap()
            mail.select("INBOX")

            # Buscar correos en los últimos 20 minutos
            date = (datetime.now() - timedelta(minutes=20)).strftime("%d-%b-%Y %H:%M:%S")
            search_criteria = f'(OR (FROM "info@account.netflix.com") (SUBJECT "Fwd: Netflix") (SUBJECT "FW: Netflix")) SINCE "{date}"'
            
            _, messages = mail.search(None, search_criteria)
            
            for num in messages[0].split():
                _, msg_data = mail.fetch(num, "(RFC822)")
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                # Verificar si el correo está relacionado con el dominio solicitado
                original_sender = self._get_original_sender(email_message)
                if original_sender and domain in original_sender:
                    # Procesar el correo según su tipo
                    if 'Hogar con Netflix' in email_message['subject']:
                        body = self._get_email_body(email_message)
                        soup = BeautifulSoup(body, 'html.parser')
                        confirm_button = soup.find(
                            'a', string=lambda text: text and (
                                'Sí, la envié yo' in text or 'Yes, it was me' in text))
                        
                        if confirm_button:
                            link = confirm_button.get('href')
                            return {
                                "has_code": True,
                                "confirmation_link": link,
                                "email": email_address,
                                "type": "netflix_home"
                            }
                    
                    elif self._is_relevant_email(email_message):
                        body = self._get_email_body(email_message)
                        code = self.code_extractor.extract_code_from_email(body)
                        if code:
                            return {
                                "has_code": True,
                                "code": code,
                                "email": email_address,
                                "type": "verification_code"
                            }
            
            return {
                "has_code": False,
                "message": "No se encontraron códigos o solicitudes pendientes",
                "email": email_address,
                "setup_required": False
            }

        except HTTPException as he:
            raise he
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

    def _get_email_body(self, email_message) -> str:
        """Extrae el cuerpo del mensaje de correo"""
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/html":
                    return part.get_payload(decode=True).decode()
        else:
            return email_message.get_payload(decode=True).decode()

    def _get_original_sender(self, email_message) -> str:
        """Extrae el remitente original de un correo reenviado"""
        try:
            # Buscar en headers de reenvío
            for header in ['Original-From', 'From']:
                if header in email_message:
                    return email_message[header]
            
            # Buscar en el cuerpo del mensaje
            body = self._get_email_body(email_message)
            if body:
                patterns = [
                    r'From:\s*([^\n]+)',
                    r'De:\s*([^\n]+)',
                    r'Sender:\s*([^\n]+)'
                ]
                for pattern in patterns:
                    match = re.search(pattern, body)
                    if match:
                        return match.group(1)
            return None
        except Exception as e:
            logger.error(f"Error extrayendo remitente original: {str(e)}")
            return None

    def _is_relevant_email(self, email_message) -> bool:
        """Verifica si el correo es relevante para la extracción de códigos"""
        subject = email_message['subject'].lower()
        relevant_subjects = [
            'código de verificación',
            'verification code',
            'código netflix',
            'netflix code',
            'fwd: netflix',
            'fw: netflix',
            'hogar con netflix'
        ]
        return any(text in subject for text in relevant_subjects)

    def _handle_unauthorized_domain(self, domain: str) -> dict:
        """Maneja el caso de dominio no autorizado"""
        return {
            "has_code": False,
            "message": f"El dominio {domain} no está autorizado",
            "email": None,
            "setup_required": True
        }