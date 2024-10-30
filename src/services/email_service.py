import imaplib
import email
from bs4 import BeautifulSoup
import re
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from src.models.email_account import EmailAccount

class EmailCodeService:
    def __init__(self, db: Session):
        self.db = db

    async def check_email_for_codes(self, email_address: str) -> dict:
        try:
            print(f"DEBUG - Buscando email: {email_address}")
            
            email_account = self.db.query(EmailAccount).filter(
                func.lower(EmailAccount.email) == func.lower(email_address)
            ).first()

            if not email_account:
                return {
                    "has_code": False,
                    "message": f"Email {email_address} no encontrado en la base de datos",
                    "setup_required": False
                }

            try:
                print(f"DEBUG - Intentando conectar a Gmail con: {email_account.email}")
                mail = imaplib.IMAP4_SSL("imap.gmail.com")
                
                try:
                    mail.login(email_account.email, email_account.password)
                except imaplib.IMAP4.error as e:
                    error_msg = str(e)
                    if "AUTHENTICATIONFAILED" in error_msg:
                        return {
                            "has_code": False,
                            "message": "Configuración de Gmail requerida",
                            "setup_required": True,
                            "setup_instructions": {
                                "title": "Necesitas configurar tu cuenta de Gmail",
                                "steps": [
                                    "1. Habilita la verificación en dos pasos:",
                                    "   - Ve a https://myaccount.google.com/security",
                                    "   - Activa 'Verificación en 2 pasos'",
                                    "2. Genera una contraseña de aplicación:",
                                    "   - Ve a https://myaccount.google.com/apppasswords",
                                    "   - Selecciona 'Otra' como aplicación",
                                    "   - Dale un nombre (ejemplo: 'Netflix Code')",
                                    "   - Copia la contraseña generada",
                                    "3. Habilita IMAP en Gmail:",
                                    "   - Ve a https://mail.google.com/mail/u/0/#settings/fwdandpop",
                                    "   - Activa 'Habilitar IMAP'",
                                    "   - Guarda los cambios"
                                ],
                                "contact_support": "Si necesitas ayuda, contacta a soporte con el código: IMAP_SETUP_REQ"
                            }
                        }

                mail.select('inbox')

                # Buscar correos de Netflix
                try:
                    _, messages = mail.search(None, '(FROM "info@netflix.com" UNSEEN)')
                    
                    message_count = len(messages[0].split())
                    print(f"DEBUG - Mensajes sin leer encontrados: {message_count}")

                    for num in messages[0].split():
                        _, msg = mail.fetch(num, '(RFC822)')
                        email_body = msg[0][1]
                        email_message = email.message_from_bytes(email_body)
                        
                        code = self._extract_netflix_code(email_message)
                        if code:
                            print(f"DEBUG - Código encontrado: {code}")
                            return {
                                "has_code": True,
                                "code": code,
                                "email": email_address
                            }

                    return {
                        "has_code": False,
                        "message": "No se encontraron códigos nuevos",
                        "email": email_address,
                        "setup_required": False
                    }

                except Exception as e:
                    return {
                        "has_code": False,
                        "message": "Error al buscar correos",
                        "error": str(e),
                        "setup_required": True,
                        "setup_instructions": {
                            "title": "Error al buscar correos de Netflix",
                            "steps": [
                                "1. Verifica que el correo de Netflix (info@netflix.com) no esté bloqueado",
                                "2. Revisa la carpeta de spam",
                                "3. Asegúrate de que el correo de Netflix llegue a la bandeja principal"
                            ]
                        }
                    }

            finally:
                try:
                    mail.logout()
                except:
                    pass

        except Exception as e:
            print(f"DEBUG - Error general: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Error interno del servidor",
                    "error": str(e),
                    "contact_support": "Por favor, contacta a soporte con el código: SERVER_ERROR"
                }
            )