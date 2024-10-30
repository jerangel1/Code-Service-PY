from sqlalchemy import Column, Integer, String, DateTime
from src.config.database import Base
from datetime import datetime

class EmailAccount(Base):
    __tablename__ = "email_accounts"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    service = Column(String, nullable=True)
    status = Column(String, default='active')
    associated_accounts = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)