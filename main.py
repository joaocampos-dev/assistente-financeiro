import json
import os

import openai
from fastapi import Depends, FastAPI, Request
from sqlmodel import SQLModel, Session
from typing import Any

from database import models
from database.database import engine
from routers.transactions import router as transactions_router

SQLModel.metadata.create_all(bind=engine)

app = FastAPI(title="Assistente Financeiro")

app.include_router(transactions_router, prefix="/transactions", tags=["Transactions"])


def get_session():
    with Session(engine) as session:
        yield session


def extract_transaction_details(user_text: str) -> dict:
    default_data = {
        "tipo": "despesa",
        "valor": 0.0,
        "descricao": "nao identificado",
        "categoria": "Outros",
    }

    try:
        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        system_prompt = (
            "Voce e um assistente financeiro especializado em extrair dados de transacoes.\n"
            "Sua unica funcao e ler a mensagem do usuario e responder APENAS com um JSON valido.\n"
            "Nao inclua explicacoes, markdown, texto adicional, comentarios, prefixos ou sufixos.\n"
            "Formato EXATO de saida:\n"
            '{"tipo": "...", "valor": ..., "descricao": "...", "categoria": "..."}\n'
            "Regras:\n"
            "- tipo deve ser 'receita' ou 'despesa'.\n"
            "- valor deve ser numero float (sem simbolo de moeda).\n"
            "- descricao deve ser curta e objetiva.\n"
            "- categoria deve ser uma categoria financeira comum.\n"
            "Exemplos de categorizacao:\n"
            "- salario, bonus, freelas -> Salario\n"
            "- mercado, restaurante, lanches -> Alimentacao\n"
            "- uber, onibus, combustivel -> Transporte\n"
            "- aluguel, condominio, luz, agua, internet -> Moradia\n"
            "- farmacia, medico, plano de saude -> Saude\n"
            "- cursos, livros, mensalidade -> Educacao\n"
            "- cinema, streaming, viagens -> Lazer\n"
            "- compras diversas -> Outros\n"
            "Se houver duvida, escolha a categoria mais provavel e mantenha JSON valido."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            temperature=0,
        )

        ai_content = response.choices[0].message.content or ""
        ai_content = ai_content.strip()

        if ai_content.startswith("```"):
            ai_content = ai_content.replace("```json", "").replace("```", "").strip()

        parsed_data = json.loads(ai_content)

        return {
            "tipo": parsed_data.get("tipo", default_data["tipo"]),
            "valor": float(parsed_data.get("valor", default_data["valor"])),
            "descricao": parsed_data.get("descricao", default_data["descricao"]),
            "categoria": parsed_data.get("categoria", default_data["categoria"]),
        }
    except Exception as error:
        print(f"Erro ao extrair detalhes da transacao com OpenAI: {error}")
        return default_data


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
async def webhook_zenvia(request: Request, session: Session = Depends(get_session)) -> dict[str, str]:
    try:
        body = await request.json()
        message = body.get("message", {})

        sender_number = message.get("from")
        visitor = message.get("visitor", {})
        visitor_name = visitor.get("name")
        contents = message.get("contents", [])
        message_text = contents[0].get("text") if contents and isinstance(contents[0], dict) else None
        transaction_data = extract_transaction_details(message_text or "")
        transaction = models.Transaction(
            tipo=transaction_data.get("tipo", ""),
            valor=transaction_data.get("valor", 0.0),
            descricao=transaction_data.get("descricao", ""),
            categoria=transaction_data.get("categoria", ""),
        )
        session.add(transaction)
        session.commit()
        session.refresh(transaction)

        print(f"MENSAGEM RECEBIDA DE: {visitor_name} ({sender_number})")
        print(f"  -> Texto Original: '{message_text}'")
        print("  --------------------")
        print("  DADOS EXTRAIDOS DA TRANSACAO:")
        print(f"  -> Tipo: {transaction_data.get('tipo')}")
        print(f"  -> Valor: {transaction_data.get('valor')}")
        print(f"  -> Descricao: {transaction_data.get('descricao')}")
        print(f"  -> Categoria: {transaction_data.get('categoria')}")
        print(f"  -> ID Salvo no Banco: {transaction.id}")
        return {"status": "message processed successfully"}
    except Exception as error:
        print(f"Erro ao processar mensagem da Zenvia: {error}")
        return {"status": "error processing message"}
