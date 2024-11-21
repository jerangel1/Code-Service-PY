from sqlalchemy import Column, Integer, String, DateTime, func
from src.config.database import Base

class AuthorizedDomain(Base):
    __tablename__ = "authorized_domains"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())