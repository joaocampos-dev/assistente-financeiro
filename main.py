from fastapi import FastAPI

from database import models
from database.database import engine
from routers.transactions import router as transactions_router

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Assistente Financeiro")

app.include_router(transactions_router, prefix="/transactions", tags=["Transactions"])


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "API do Assistente Financeiro no ar!"}
