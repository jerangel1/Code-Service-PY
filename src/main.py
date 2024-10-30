from fastapi import FastAPI, BackgroundTasks
from sqlalchemy.orm import Session
from .config.database import SessionLocal
from .models.email_account import EmailAccount
from .services.email_service import EmailService

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/check-codes")
async def check_netflix_codes(background_tasks: BackgroundTasks):
    db = next(get_db())
    email_accounts = db.query(EmailAccount).all()
    results = []

    for account in email_accounts:
        email_service = EmailService(account.email, account.password)
        if email_service.connect():
            codes = email_service.check_for_netflix_codes()
            if codes:
                results.append({
                    'email': account.email,
                    'codes': codes
                })

    return results