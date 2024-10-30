from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.models.email_account import EmailAccount
from src.services.email_service import EmailCodeService

app = FastAPI()

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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