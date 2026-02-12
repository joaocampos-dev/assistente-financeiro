from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import Transaction

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
    transaction = Transaction(
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


@router.get("/", response_model=list[TransactionResponse])
def list_transactions(db: Session = Depends(get_db)):
    transactions = db.query(Transaction).all()
    return [
        TransactionResponse(
            id=transaction.id,
            description=transaction.descricao,
            amount=transaction.valor,
            category=transaction.categoria,
            date_created=transaction.data_criacao,
        )
        for transaction in transactions
    ]


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transacao nao encontrada")
    return TransactionResponse(
        id=transaction.id,
        description=transaction.descricao,
        amount=transaction.valor,
        category=transaction.categoria,
        date_created=transaction.data_criacao,
    )


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transacao nao encontrada")

    db.delete(transaction)
    db.commit()
    return None
