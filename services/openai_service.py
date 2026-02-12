import json
import os
from typing import Any

import openai


async def analyze_query(user_message: str) -> dict[str, Any]:
    default_result: dict[str, Any] = {"aggregation": "list", "filters": {}}

    try:
        client = openai.AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        system_prompt = (
            "Voce e uma especialista em analise de queries para um banco de dados de financas.\n"
            "A data de hoje e 12 de Fevereiro de 2026.\n"
            "Sua tarefa e transformar a pergunta do usuario em um JSON estruturado para consulta.\n"
            "Responda APENAS com um objeto JSON valido, sem markdown e sem texto extra.\n"
            "Formato esperado:\n"
            "{\n"
            '  "aggregation": "sum" ou "list",\n'
            '  "filters": {\n'
            '    "date_start": "YYYY-MM-DD",\n'
            '    "date_end": "YYYY-MM-DD",\n'
            '    "tipo": "receita" ou "despesa",\n'
            '    "categoria": "nome da categoria"\n'
            "  },\n"
            '  "limit": numero (opcional)\n'
            "}\n"
            "Regras:\n"
            "- aggregation = 'sum' para perguntas de total/quanto gastei/quanto recebi.\n"
            "- aggregation = 'list' para perguntas de listar, mostrar, ultimas transacoes.\n"
            "- Se algum filtro nao for mencionado, nao inclua a chave.\n"
            "- Use datas no formato YYYY-MM-DD.\n"
            "- Para periodos relativos (hoje, este mes, fevereiro), converta para datas absolutas.\n"
            "Exemplos:\n"
            'Mensagem: "quanto gastei hoje?" -> {"aggregation": "sum", "filters": {"tipo": "despesa", "date_start": "2026-02-12", "date_end": "2026-02-12"}}\n'
            'Mensagem: "listar minhas receitas de fevereiro" -> {"aggregation": "list", "filters": {"tipo": "receita", "date_start": "2026-02-01", "date_end": "2026-02-28"}}\n'
            'Mensagem: "total de despesas com alimentação este mês" -> {"aggregation": "sum", "filters": {"tipo": "despesa", "categoria": "Alimentacao", "date_start": "2026-02-01", "date_end": "2026-02-28"}}\n'
            'Mensagem: "últimas 3 transações" -> {"aggregation": "list", "filters": {}, "limit": 3}'
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
        if not isinstance(parsed, dict):
            return default_result

        aggregation = parsed.get("aggregation")
        filters = parsed.get("filters")
        limit = parsed.get("limit")

        result: dict[str, Any] = {
            "aggregation": aggregation if aggregation in {"sum", "list"} else "list",
            "filters": filters if isinstance(filters, dict) else {},
        }
        if isinstance(limit, int):
            result["limit"] = limit

        return result
    except Exception as error:
        print(f"Erro ao analisar query com OpenAI: {error}")
        return default_result
