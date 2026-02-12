from sqlalchemy import Column, DateTime, Float, Integer, String, func

from database.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String, nullable=True)
    date_created = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
