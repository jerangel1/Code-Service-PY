import socket
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import imaplib
import os
from typing import Optional

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
    """Endpoint de salud"""
    try:
        return {"status": "ok", "message": "API funcionando"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/check-code/{email}")
async def check_code(email: str, db: Session = Depends(get_db)):
    """Endpoint para buscar códigos de verificación"""
    try:
        service = EmailCodeService(db)
        result = await service.check_email_for_codes(email)
        return result
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/test-auth")
async def test_auth(db: Session = Depends(get_db)):
    """Endpoint para probar la conexión al correo central"""
    try:
        service = EmailCodeService(db)
        mail = service._connect_to_imap()
        
        if mail:
            mail.select("INBOX")
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
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error de conexión: {str(e)}"
        )

# Nuevos endpoints para gestión de dominios autorizados

@app.post("/api/authorized-domains")
async def add_authorized_domain(domain: str, db: Session = Depends(get_db)):
    """
    Agrega un nuevo dominio autorizado
    
    Args:
        domain: Dominio a autorizar (ejemplo: example.com)
    """
    try:
        service = EmailCodeService(db)
        result = await service.add_authorized_domain(domain)
        return result
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al agregar dominio: {str(e)}"
        )

@app.delete("/api/authorized-domains/{domain}")
async def remove_authorized_domain(domain: str, db: Session = Depends(get_db)):
    """
    Elimina un dominio autorizado
    
    Args:
        domain: Dominio a eliminar (ejemplo: example.com)
    """
    try:
        service = EmailCodeService(db)
        result = await service.remove_authorized_domain(domain)
        return result
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar dominio: {str(e)}"
        )

@app.get("/api/authorized-domains")
async def get_authorized_domains(db: Session = Depends(get_db)):
    """Lista todos los dominios autorizados"""
    try:
        service = EmailCodeService(db)
        domains = await service.get_authorized_domains()
        return {
            "status": "success",
            "domains": domains
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener dominios: {str(e)}"
        )

@app.get("/api/check-domain/{domain}")
async def check_domain_authorization(domain: str, db: Session = Depends(get_db)):
    """
    Verifica si un dominio está autorizado
    
    Args:
        domain: Dominio a verificar (ejemplo: example.com)
    """
    try:
        service = EmailCodeService(db)
        is_authorized = domain.lower() in service.authorized_domains
        return {
            "domain": domain,
            "is_authorized": is_authorized
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al verificar dominio: {str(e)}"
        )