from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.models.email_account import EmailAccount
from src.services.email_service import EmailCodeService
import os


app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS"),
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Especificamos los métodos
    allow_headers=["*"],
    expose_headers=["*"],  # Agregamos headers expuestos
    max_age=3600,
)

@app.get("/")
async def root():
    return {"message": "API funcionando"}

@app.get("/api/check-code/{email}")
async def check_code(email: str, db: Session = Depends(get_db)):
    print(f"DEBUG - Endpoint llamado con email: {email}")
    service = EmailCodeService(db)
    result = await service.check_email_for_codes(email)
    print(f"DEBUG - Resultado: {result}")
    return result