from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.models.email_account import EmailAccount
import imaplib
import email
from datetime import datetime, timedelta
from .code_extractor import CodeExtractor
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class EmailCodeService:
    def __init__(self, db: Session):
        self.db = db
        self.code_extractor = CodeExtractor()

    async def check_email_for_codes(self, email_address: str) -> dict:
        try:
            logger.info(f"📧 Buscando email: {email_address}")
            
            # 1. Validar si el correo existe en la DB
            email_account = self.db.query(EmailAccount).filter(
                func.lower(EmailAccount.email) == func.lower(email_address)
            ).first()

            if not email_account:
                logger.warning(f"❌ Email no encontrado en DB: {email_address}")
                return {
                    "has_code": False,
                    "message": f"Email {email_address} no encontrado en la base de datos",
                    "setup_required": False
                }

            try:
                # 2. Conectar a Office 365 (GoDaddy)
                logger.info(f"🔄 Conectando a Office 365: {email_account.email}")
                mail = imaplib.IMAP4_SSL("outlook.office365.com", 993)
                
                try:
                    mail.login(email_account.email, email_account.password)
                except imaplib.IMAP4.error as e:
                    return self._handle_auth_error(str(e))

                # 3. Seleccionar bandeja de entrada y buscar correos
                mail.select('INBOX')

                # Buscar correos recientes de Netflix (últimas 24 horas)
                date = (datetime.now() - timedelta(days=1)).strftime("%d-%b-%Y")
                search_criteria = f'(SINCE "{date}" FROM "info@account.netflix.com" UNSEEN)'
                
                _, messages = mail.search(None, search_criteria)
                
                message_count = len(messages[0].split())
                logger.info(f"📨 Correos de Netflix encontrados: {message_count}")

                for num in messages[0].split():
                    _, msg = mail.fetch(num, '(RFC822)')
                    email_body = msg[0][1]
                    email_message = email.message_from_bytes(email_body)
                    
                    # 4. Verificar tipo de correo y procesar
                    if self._is_netflix_home_email(email_message):
                        link = self._extract_confirmation_link(email_message)
                        if link:
                            logger.info(f"✅ Enlace de confirmación de Hogar encontrado")
                            return {
                                "has_code": True,
                                "confirmation_link": link,
                                "email": email_address,
                                "type": "netflix_home"
                            }
                    elif self._is_relevant_email(email_message):
                        code = self.code_extractor.extract_code_from_email(email_message)
                        if code:
                            logger.info(f"✅ Código encontrado: {code}")
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

            finally:
                try:
                    mail.logout()
                except:
                    pass

        except Exception as e:
            logger.error(f"❌ Error general: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Error interno del servidor",
                    "error": str(e)
                }
            )

    def _is_netflix_home_email(self, email_message) -> bool:
        """Verifica si el correo es específicamente de Hogar con Netflix."""
        subject = email_message.get('Subject', '')
        from_address = email_message.get('From', '')
        return (
            'info@account.netflix.com' in from_address.lower() and
            'Hogar con Netflix' in subject
        )

    def _is_relevant_email(self, email_message) -> bool:
        """Verifica si el correo es relevante para otros tipos de códigos."""
        relevant_senders = [
            "@serviciosnp.com",
            "@account.netflix.com",
            "@netflix.com"
        ]
        
        sender = email_message.get('From', '')
        subject = email_message.get('Subject', '')
        
        keywords = [
            'código', 
            'verificación', 
            'verification', 
            'code',
            'acceso',
            'access',
            'temporal'
        ]
        
        return any(domain in sender.lower() for domain in relevant_senders) and \
               any(keyword in subject.lower() for keyword in keywords)

    def _extract_confirmation_link(self, email_message) -> str:
        """Extrae el enlace de confirmación del correo de Hogar con Netflix."""
        try:
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/html":
                        body = part.get_payload(decode=True).decode()
                        soup = BeautifulSoup(body, 'html.parser')
                        
                        # Buscar el botón "Sí, la envié yo"
                        confirm_button = soup.find('a', string=lambda text: 
                            text and ('Sí, la envié yo' in text or 'Yes, it was me' in text))
                        
                        if confirm_button:
                            return confirm_button.get('href')
            return None
        except Exception as e:
            logger.error(f"Error extrayendo enlace: {str(e)}")
            return None

    def _handle_auth_error(self, error_msg: str) -> dict:
        """Maneja errores de autenticación específicos de GoDaddy Office 365."""
        return {
            "has_code": False,
            "message": "Configuración de Office 365 requerida",
            "setup_required": True,
            "setup_instructions": {
                "title": "Necesitas configurar tu cuenta de Office 365",
                "steps": [
                    "1. Verifica tus credenciales en GoDaddy SSO",
                    "2. Habilita el acceso IMAP en Office 365:",
                    "   - Inicia sesión en outlook.office365.com",
                    "   - Ve a Configuración > Todas las configuraciones",
                    "   - Busca 'POP e IMAP'",
                    "   - Habilita IMAP",
                    "3. Si usas autenticación de dos factores:",
                    "   - Genera una contraseña de aplicación",
                    "   - Usa esa contraseña en lugar de tu contraseña normal"
                ],
                "contact_support": "Si necesitas ayuda, contacta a soporte con el código: GODADDY_O365_SETUP"
            }
        }