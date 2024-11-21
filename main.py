from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import os
from datetime import datetime

from src.config.database import get_db
from src.services.email_service import EmailCodeService

app = FastAPI(
    title="Netflix Code Service API",
    description="API para gestionar códigos de verificación de Netflix",
    version="2.0.0",
    docs_url="/docs",
    redoc_url=None
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "").split(","),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

@app.get("/", include_in_schema=False)
async def root():
    """Redirecciona a la documentación de la API"""
    return RedirectResponse(url="/docs")

@app.get("/api/status")
async def check_status():
    """
    Endpoint de estado del servicio
    
    Returns:
        dict: Estado actual del servicio y metadata
    """
    try:
        return {
            "status": "operational",
            "service": "Netflix Code Service",
            "version": "2.0.0",
            "timestamp": datetime.now().isoformat(),
            "environment": os.getenv("ENVIRONMENT", "production"),
            "metadata": {
                "docs": "/docs",
                "health": "ok",
                "maintenance_mode": False
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Error al verificar estado del servicio",
                "error": str(e)
            }
        )

@app.get("/api/check-code/{email}")
async def check_code(email: str, db: Session = Depends(get_db)):
    """
    Busca códigos de verificación de Netflix para un email específico
    
    Args:
        email: Correo electrónico para buscar códigos
    
    Returns:
        dict: Información sobre el código encontrado o mensaje si no hay códigos
    
    Raises:
        HTTPException: Si ocurre un error durante la búsqueda
    """
    try:
        service = EmailCodeService(db)
        result = await service.check_email_for_codes(email)
        return {
            "status": "success",
            "data": result,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "message": "Error al buscar códigos",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

@app.get("/api/test-auth")
async def test_auth(db: Session = Depends(get_db)):
    """
    Prueba la conexión al servidor de correo central
    
    Returns:
        dict: Estado de la conexión y detalles de configuración
    
    Raises:
        HTTPException: Si hay problemas de conexión
    """
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
                "timestamp": datetime.now().isoformat(),
                "data": {
                    "email": service.central_email,
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
            detail={
                "status": "error",
                "message": "Error de conexión con Gmail",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )