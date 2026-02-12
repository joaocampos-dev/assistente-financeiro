from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    tipo: str
    valor: float
    descricao: str
    categoria: str
    data_criacao: datetime = Field(default_factory=datetime.utcnow, nullable=False)
