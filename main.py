import json
from fastapi import FastAPI, Request
from typing import Any

from database import models
from database.database import engine
from routers.transactions import router as transactions_router

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Assistente Financeiro")

app.include_router(transactions_router, prefix="/transactions", tags=["Transactions"])


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "API do Assistente Financeiro no ar!"}


@app.post("/zenvia-webhook")
def receive_zenvia_webhook(payload: dict[str, Any]) -> dict[str, str]:
    sender = payload.get("from")
    message = payload.get("message", {})
    contents = message.get("contents", [])
    text = contents[0].get("text") if contents and isinstance(contents[0], dict) else None

    print(f"[ZENVIA] Remetente: {sender} | Mensagem: {text}")
    return {"status": "received"}


@app.post("/webhook/zenvia")
async def webhook_zenvia(request: Request) -> dict[str, str]:
    body = await request.json()

    print("========== MENSAGEM RECEBIDA DA ZENVIA ==========")
    print(json.dumps(body, indent=2, ensure_ascii=False))
    print("==================================================")

    return {"status": "message received successfully"}
