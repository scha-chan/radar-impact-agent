FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY knowledge/ knowledge/

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Sem API ainda (card 30) - o entrypoint padrao e o servidor MCP
# (stdio, card 07). `docker compose up` (RNF-06) usa este mesmo build.
CMD ["python", "-m", "src.mcp_server.server"]
