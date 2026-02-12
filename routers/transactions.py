from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from database import models
from database.database import get_db, get_session

router = APIRouter()


class TransactionCreate(BaseModel):
    tipo: str = "despesa"
    description: str
    amount: float
    category: str | None = None


class TransactionResponse(BaseModel):
    id: int
    description: str
    amount: float
    category: str | None
    date_created: datetime

    class Config:
        from_attributes = True


@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(payload: TransactionCreate, db: Session = Depends(get_db)):
    transaction = models.Transaction(
        tipo=payload.tipo,
        valor=payload.amount,
        descricao=payload.description,
        categoria=payload.category or "Sem categoria",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return TransactionResponse(
        id=transaction.id,
        description=transaction.descricao,
        amount=transaction.valor,
        category=transaction.categoria,
        date_created=transaction.data_criacao,
    )


@router.get("/", response_model=list[models.Transaction])
def get_all_transactions(session: Session = Depends(get_session)) -> List[models.Transaction]:
    transactions = session.exec(select(models.Transaction)).all()
    return transactions


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    transaction = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transacao nao encontrada")
    return TransactionResponse(
        id=transaction.id,
        description=transaction.descricao,
        amount=transaction.valor,
        category=transaction.categoria,
        date_created=transaction.data_criacao,
    )


@router.delete("/{transaction_id}")
def delete_transaction(transaction_id: int, session: Session = Depends(get_session)):
    transaction = session.get(models.Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transacao nao encontrada")

    session.delete(transaction)
    session.commit()
    return {"ok": True}
