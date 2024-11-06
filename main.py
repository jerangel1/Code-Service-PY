from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.models.email_account import EmailAccount
from src.services.email_service import EmailCodeService
import os
import logging
import sys

# Configuración mejorada de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log')  # También guardamos logs en archivo
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Log inicial de la aplicación
logger.info("🚀 Iniciando aplicación...")

# Configurar CORS con mejor logging
origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
origins = [origin.strip() for origin in origins if origin.strip()]
logger.info(f"🔒 CORS configurado con orígenes: {origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    # Log detallado de cada petición
    logger.info("➡️ Nueva petición recibida")
    logger.info(f"📍 Método: {request.method} | URL: {request.url}")
    logger.debug(f"🔍 Headers: {dict(request.headers)}")
    
    try:
        response = await call_next(request)
        logger.info(f"✅ Respuesta enviada: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"❌ Error en middleware: {str(e)}")
        raise

@app.get("/")
async def root():
    logger.info("📌 Endpoint raíz llamado")
    return {"message": "API funcionando", "status": "ok"}

@app.get("/api/check-code/{email}")
async def check_code(email: str, request: Request, db: Session = Depends(get_db)):
    try:
        logger.info(f"📧 Verificando email: {email}")
        logger.debug(f"🔍 Headers de la petición: {dict(request.headers)}")
        logger.debug(f"🌐 Origen: {request.headers.get('origin')}")
        
        service = EmailCodeService(db)
        result = await service.check_email_for_codes(email)
        
        logger.info(f"📊 Resultado: {result}")
        return result
    except Exception as e:
        error_msg = f"❌ Error procesando email {email}: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

# Endpoint adicional para debug de CORS
@app.options("/api/check-code/{email}")
async def options_check_code(email: str, request: Request):
    logger.info(f"🔄 Preflight request para email: {email}")
    logger.debug(f"🔍 Headers preflight: {dict(request.headers)}")
    return {}