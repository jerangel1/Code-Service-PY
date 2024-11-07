from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from src.models.email_account import EmailAccount
from datetime import datetime, timedelta
from .code_extractor import CodeExtractor
from bs4 import BeautifulSoup
import logging
import os
from O365 import Account, Connection

logger = logging.getLogger(__name__)

class EmailCodeService:
    def __init__(self, db: Session):
        self.db = db
        self.code_extractor = CodeExtractor()
        self.client_id = os.getenv('MS_CLIENT_ID')
        self.client_secret = os.getenv('MS_CLIENT_SECRET')
        self.tenant_id = os.getenv('MS_TENANT_ID')
        
        # Agregar lista de dominios autorizados
        self.authorized_domains = [
            'serviciosnp.com',
            'nplus600.com',
            'smartservicesnp.com',
            'snp2022.xyz'
        ]
    
    async def check_email_for_codes(self, email_address: str) -> dict:
        try:
            # Validar dominio del correo
            domain = email_address.split('@')[1].lower()
            if domain not in self.authorized_domains:
                logger.warning(f"❌ Dominio no autorizado: {domain}")
                return {
                    "has_code": False,
                    "message": f"El dominio {domain} no está autorizado",
                    "setup_required": True,
                    "setup_instructions": {
                        "title": "Dominio no configurado en Azure",
                        "steps": [
                            "1. Verifica que el dominio esté agregado en Azure",
                            "2. Completa la configuración DNS del dominio",
                            "3. Espera a que la verificación se complete (15-30 min)",
                            "4. Contacta al administrador si el problema persiste"
                        ],
                        "contact_support": "support@serviciosnp.com"
                    }
                }

            logger.info(f"📧 Buscando email en DB: {email_address}")


            # 1. Validar correo en DB
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
                # 2. Configurar conexión OAuth2 usando las credenciales del .env
                credentials = (self.client_id, self.client_secret)
                account = Account(
                    credentials,
                    auth_flow_type='credentials',
                    tenant_id=self.tenant_id)

                if account.authenticate():
                    mailbox = account.mailbox()
                    logger.info("✅ Autenticación exitosa con Microsoft")


                    # 3. Buscar correos de Netflix (últimas 24 horas)
                    yesterday = datetime.now() - timedelta(days=1)
                    query = (
                        f"from:info@account.netflix.com "
                        f"AND received>={yesterday.strftime('%Y-%m-%d')} "
                        f"AND (subject:'Hogar con Netflix' OR subject:'código')")

                    messages = mailbox.get_messages(query=query, limit=10)
                    logger.info("🔍 Buscando correos de Netflix")
                    
                    for message in messages:
                        # Verificar si es correo de Hogar Netflix
                        if 'Hogar con Netflix' in message.subject:
                            body = message.get_body_text()
                            soup = BeautifulSoup(body, 'html.parser')
                            confirm_button = soup.find(
                                'a', string=lambda text: text and (
                                    'Sí, la envié yo' in text or 'Yes, it was me' in text))

                            if confirm_button:
                                link = confirm_button.get('href')
                                logger.info(f"✅ Enlace de confirmación encontrado: {link}")
                                return {
                                    "has_code": True,
                                    "confirmation_link": link,
                                    "email": email_address,
                                    "type": "netflix_home"
                                }

                        # Buscar códigos de verificación
                        elif any(keyword in message.subject.lower() 
                            for keyword in ['código', 'code', 'verificación']):
                            body = message.get_body_text()
                            code = self.code_extractor.extract_code_from_email(body)
                            if code:
                                logger.info(f"✅ Código encontrado: {code}")
                                return {
                                    "has_code": True,
                                    "code": code,
                                    "email": email_address,
                                    "type": "verification_code"
                                }

                    logger.info("ℹ️ No se encontraron códigos o solicitudes")
                    return {
                        "has_code": False,
                        "message": "No se encontraron códigos o solicitudes pendientes",
                        "email": email_address,
                        "setup_required": False
                    }
                else:
                    logger.error("❌ Error de autenticación con Microsoft")
                    return self._handle_auth_error("No se pudo autenticar")

            except Exception as e:
                logger.error(f"❌ Error accediendo al correo: {str(e)}")
                return self._handle_auth_error(str(e))

        except Exception as e:
            logger.error(f"❌ Error general: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

    def _is_relevant_email(self, message) -> bool:
        """Verifica si el correo es relevante para códigos."""
        subject = message.subject.lower()
        return any(keyword in subject for keyword in [
            'código', 
            'verificación', 
            'verification', 
            'code',
            'acceso',
            'access'
        ])

    def _handle_auth_error(self, error_msg: str) -> dict:
        return {
            "has_code": False,
            "message": "Error de autenticación con Microsoft",
            "setup_required": True,
            "setup_instructions": {
                "title": "Verifica la configuración de Microsoft",
                "steps": [
                    "1. Verifica que las credenciales en .env sean correctas",
                    "2. Asegúrate que los permisos estén concedidos en Azure",
                    "3. Verifica que el tenant_id sea el correcto"
                ],
                "error": str(error_msg),
                "contact_support": "support@serviciosnp.com"
            }
        }