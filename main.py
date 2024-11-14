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
        mail = imaplib.IMAP4_SSL(service.imap_server, service.imap_port)
        mail.login(service.central_email, service.central_password)
        mail.select("INBOX")
        
        # Si la conexión es exitosa, cerrar correctamente
        mail.close()
        mail.logout()
        
        return {
            "status": "success",
            "message": "Autenticación exitosa con Gmail",
            "email": service.central_email
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error de autenticación: {str(e)}"
        }