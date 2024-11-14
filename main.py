from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import imaplib
import os

# Corregir las importaciones
from src.config.database import get_db
from src.models.email_account import EmailAccount
from src.services.email_service import EmailCodeService

app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS"),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

@app.get("/")
async def root():
    return {"message": "API funcionando"}

@app.get("/api/check-code/{email}")
async def check_code(email: str, db: Session = Depends(get_db)):
    """Endpoint para buscar códigos de verificación"""
    print(f"DEBUG - Endpoint llamado con email: {email}")
    service = EmailCodeService(db)
    result = await service.check_email_for_codes(email)
    print(f"DEBUG - Resultado: {result}")
    return result

@app.get("/api/test-auth")
async def test_auth(db: Session = Depends(get_db)):
    """Endpoint para probar la conexión al correo central"""
    try:
        service = EmailCodeService(db)
        
        # Verificar que existe la configuración básica
        if not service.central_email or not service.central_password:
            return {
                "status": "error",
                "message": "Falta configuración del correo central en la base de datos"
            }

        try:
            # Intentar conexión IMAP
            mail = imaplib.IMAP4_SSL(service.imap_server, service.imap_port)
        except Exception as imap_error:
            return {
                "status": "error",
                "message": f"Error de conexión IMAP: No se puede conectar al servidor Gmail. Verifique su conexión a internet",
                "details": str(imap_error)
            }

        try:
            # Intentar login
            mail.login(service.central_email, service.central_password)
        except imaplib.IMAP4.error as login_error:
            return {
                "status": "error",
                "message": "Error de autenticación: Credenciales incorrectas. Verifique el correo y la contraseña",
                "details": str(login_error)
            }

        try:
            # Intentar seleccionar bandeja
            mail.select("INBOX")
            
            # Si todo es exitoso, cerrar correctamente
            mail.close()
            mail.logout()
            
            return {
                "status": "success",
                "message": "Conexión exitosa con Gmail",
                "email": service.central_email,
                "details": {
                    "imap_server": service.imap_server,
                    "imap_port": service.imap_port,
                    "inbox_access": True
                }
            }
        except Exception as inbox_error:
            return {
                "status": "error",
                "message": "Error accediendo al buzón de entrada",
                "details": str(inbox_error)
            }

    except Exception as e:
        return {
            "status": "error",
            "message": "Error general en la configuración del servicio",
            "details": str(e)
        }