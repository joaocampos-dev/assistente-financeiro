import json
import os
from datetime import datetime

import openai
import requests
from fastapi import Depends, FastAPI, Request
from sqlmodel import SQLModel, Session, func, select
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


async def get_intent(user_message: str) -> str | None:
    try:
        client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        system_prompt = (
            "Voce e um classificador de intencao para um assistente financeiro.\n"
            "Classifique a mensagem do usuario em apenas uma das categorias:\n"
            "- new_transaction\n"
            "- query_transactions\n"
            "Responda APENAS com JSON valido no formato exato:\n"
            '{"intent": "new_transaction"}\n'
            "ou\n"
            '{"intent": "query_transactions"}\n'
            "Nao inclua explicacoes, markdown ou texto adicional.\n"
            "Exemplos:\n"
            'Mensagem: "gastei 50 reais com o almoço" -> Resposta JSON: {"intent": "new_transaction"}\n'
            'Mensagem: "quanto eu gastei hoje?" -> Resposta JSON: {"intent": "query_transactions"}\n'
            'Mensagem: "recebi 1200 de um projeto" -> Resposta JSON: {"intent": "new_transaction"}\n'
            'Mensagem: "liste minhas últimas 5 receitas" -> Resposta JSON: {"intent": "query_transactions"}'
        )

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
        )

        content = (response.choices[0].message.content or "").strip()
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(content)
        intent = parsed.get("intent")
        if intent in {"new_transaction", "query_transactions"}:
            return intent
        return None
    except Exception as error:
        print(f"Erro ao classificar intencao com OpenAI: {error}")
        return None


def send_reply(to: str, message: str) -> None:
    zenvia_api_token = os.environ.get("ZENVIA_API_TOKEN")
    zenvia_sender_id = os.environ.get("ZENVIA_SENDER_ID")
    url = "https://api.zenvia.com/v2/channels/whatsapp/messages"

    if not zenvia_api_token or not zenvia_sender_id:
        print("Erro ao enviar resposta: variaveis ZENVIA_API_TOKEN ou ZENVIA_SENDER_ID nao configuradas.")
        return

    headers = {
        "Content-Type": "application/json",
        "X-API-TOKEN": zenvia_api_token,
    }

    data = {
        "from": zenvia_sender_id,
        "to": to,
        "contents": [
            {
                "type": "text",
                "text": message,
            }
        ],
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        response.raise_for_status()
        print(f"Resposta enviada com sucesso para {to}. Status: {response.status_code}")
    except requests.RequestException as error:
        print(f"Erro ao enviar resposta para {to}: {error}")


async def analyze_query(user_message: str) -> dict | None:
    """
    Usa a OpenAI para analisar uma pergunta do usuário e extrair parâmetros
    estruturados para uma consulta ao banco de dados.
    """
    try:
        client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        # Note o uso de ''' para um bloco de texto grande.
        # Dentro dele, aspas duplas " podem ser usadas normalmente.
        system_prompt = '''
        Você é um especialista em análise de queries para um banco de dados de finanças.
        A data de hoje é 12 de Fevereiro de 2026.
        Sua tarefa é analisar a pergunta do usuário e retornar APENAS um objeto JSON com um plano de consulta.

        As chaves JSON possíveis são:
        - "aggregation": Obrigatória. Pode ser "sum" ou "list".
        - "filters": Um objeto com filtros opcionais.
        - "limit": Um número, se o usuário pedir um limite (ex: "últimas 5").

        Os filtros possíveis dentro de "filters" são:
        - "date_start" e "date_end": Datas no formato "YYYY-MM-DD".
        - "tipo": "receita" ou "despesa".
        - "categoria": Uma categoria financeira comum.

        Exemplos de conversão de pergunta para JSON:
        - Pergunta: "quanto gastei hoje?" -> Resposta: {"aggregation": "sum", "filters": {"tipo": "despesa", "date_start": "2026-02-12", "date_end": "2026-02-12"}}
        - Pergunta: "listar minhas receitas de fevereiro" -> Resposta: {"aggregation": "list", "filters": {"tipo": "receita", "date_start": "2026-02-01", "date_end": "2026-02-28"}}
        - Pergunta: "total de despesas com alimentação este mês" -> Resposta: {"aggregation": "sum", "filters": {"tipo": "despesa", "categoria": "Alimentacao", "date_start": "2026-02-01", "date_end": "2026-02-28"}}
        - Pergunta: "últimas 3 transações" -> Resposta: {"aggregation": "list", "filters": {}, "limit": 3}
        - Pergunta: "quais foram minhas receitas?" -> Resposta: {"aggregation": "list", "filters": {"tipo": "receita"}}
        '''

        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0,
            # Forçar a resposta em formato JSON é mais confiável
            response_format={"type": "json_object"},
        )

        content = (response.choices[0].message.content or "").strip()
        return json.loads(content)

    except Exception as error:
        print(f"Erro ao analisar query com OpenAI: {error}")
        return None


def query_database(query_plan: dict, session: Session) -> Any:
    """
    Executa uma consulta no banco de dados com base em um plano gerado pela IA.
    """
    filters_data = query_plan.get("filters", {})
    aggregation = query_plan.get("aggregation")
    limit = query_plan.get("limit")

    # Define a base da consulta
    if aggregation == "sum":
        statement = select(func.sum(models.Transaction.valor))
    else:  # "list"
        statement = select(models.Transaction)

    # Aplica os filtros dinamicamente
    for key, value in filters_data.items():
        if key == "date_start":
            statement = statement.where(models.Transaction.data_criacao >= datetime.fromisoformat(value))
        elif key == "date_end":
            # Adiciona 1 dia para incluir o dia inteiro na consulta
            end_date = datetime.fromisoformat(value).replace(hour=23, minute=59, second=59)
            statement = statement.where(models.Transaction.data_criacao <= end_date)
        elif key == "tipo":
            statement = statement.where(models.Transaction.tipo == value)
        elif key == "categoria":
            statement = statement.where(models.Transaction.categoria == value)

    # Aplica ordenação e limite para listagens
    if aggregation == "list":
        statement = statement.order_by(models.Transaction.data_criacao.desc())
        if limit:
            statement = statement.limit(limit)

    # Executa a consulta
    results = session.exec(statement)

    if aggregation == "sum":
        # .one_or_none() retorna o valor ou None se não houver resultado
        return results.one_or_none() or 0.0
    else:  # "list"
        return results.all()


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
        user_message = contents[0].get("text") if contents and isinstance(contents[0], dict) else ""
        intent = await get_intent(user_message)

        if intent == "new_transaction":
            transaction_data = extract_transaction_details(user_message)
            transaction = models.Transaction(
                tipo=transaction_data.get("tipo", ""),
                valor=transaction_data.get("valor", 0.0),
                descricao=transaction_data.get("descricao", ""),
                categoria=transaction_data.get("categoria", ""),
            )
            session.add(transaction)
            session.commit()
            session.refresh(transaction)
            confirmation_message = (
                f"✅ Transacao registrada: {transaction.descricao} no valor de R$ {transaction.valor:.2f}."
            )
            send_reply(to=sender_number or "", message=confirmation_message)

            print(f"MENSAGEM RECEBIDA DE: {visitor_name} ({sender_number})")
            print(f"  -> Texto Original: '{user_message}'")
            print("  --------------------")
            print("  DADOS EXTRAIDOS DA TRANSACAO:")
            print(f"  -> Tipo: {transaction_data.get('tipo')}")
            print(f"  -> Valor: {transaction_data.get('valor')}")
            print(f"  -> Descricao: {transaction_data.get('descricao')}")
            print(f"  -> Categoria: {transaction_data.get('categoria')}")
            print(f"  -> ID Salvo no Banco: {transaction.id}")
        elif intent == "query_transactions":
            query_plan = await analyze_query(user_message)
            if query_plan is not None:
                results = query_database(query_plan, session)
                send_reply(
                    to=sender_number or "",
                    message=f"Plano: {query_plan}\n\nResultado: {results}",
                )
            else:
                send_reply(
                    to=sender_number or "",
                    message="Não consegui entender sua pergunta.",
                )
        else:
            send_reply(
                to=sender_number or "",
                message="Desculpe, não consegui entender sua solicitação.",
            )

        return {"status": "message processed successfully"}
    except Exception as error:
        print(f"Erro ao processar mensagem da Zenvia: {error}")
        return {"status": "error processing message"}
