from fastapi import FastAPI, Request
from typing import Any

from database import models
from database.database import engine
from routers.transactions import router as transactions_router

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Assistente Financeiro")

app.include_router(transactions_router, prefix="/transactions", tags=["Transactions"])


def extract_transaction_details(user_text: str) -> dict:
    # Simulacao (mock): no futuro esta funcao sera substituida por uma chamada real a uma API de LLM.
    return {
        "tipo": "receita",
        "valor": 1500.00,
        "descricao": "salario",
        "categoria": "Salario",
    }


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
    try:
        body = await request.json()
        message = body.get("message", {})

        sender_number = message.get("from")
        visitor = message.get("visitor", {})
        visitor_name = visitor.get("name")
        contents = message.get("contents", [])
        message_text = contents[0].get("text") if contents and isinstance(contents[0], dict) else None
        transaction_data = extract_transaction_details(message_text or "")

        print(f"MENSAGEM RECEBIDA DE: {visitor_name} ({sender_number})")
        print(f"  -> Texto Original: '{message_text}'")
        print("  --------------------")
        print("  DADOS EXTRAIDOS DA TRANSACAO:")
        print(f"  -> Tipo: {transaction_data.get('tipo')}")
        print(f"  -> Valor: {transaction_data.get('valor')}")
        print(f"  -> Descricao: {transaction_data.get('descricao')}")
        print(f"  -> Categoria: {transaction_data.get('categoria')}")
        return {"status": "message processed successfully"}
    except Exception as error:
        print(f"Erro ao processar mensagem da Zenvia: {error}")
        return {"status": "error processing message"}
