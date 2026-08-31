"""Carrega variáveis de ambiente de `.env` uma única vez, na importação.

Módulos que leem `os.getenv` para configuração (`graph/llm.py`,
`mcp_server/tools/*`) importam este módulo primeiro (só pelo efeito
colateral) — garante que `cp .env.example .env` (README) realmente
tenha efeito, sem precisar exportar as variáveis manualmente no shell.
"""

from dotenv import load_dotenv

load_dotenv()
