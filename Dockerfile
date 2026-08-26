FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY knowledge/ knowledge/

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Achado do card 26 (analise do log do job "build" da CI): pip avisava
# "Running pip as the 'root' user can result in broken permissions" - a
# imagem rodava como root por padrao. Cria um usuario sem privilegios para
# o processo da aplicacao; a instalacao de pacotes continua como root (a
# camada acima), so o CMD final roda sem privilegios.
RUN useradd --create-home --shell /bin/bash radar
USER radar

# Sem API ainda (card 30) - o entrypoint padrao e o servidor MCP
# (stdio, card 07). `docker compose up` (RNF-06) usa este mesmo build.
CMD ["python", "-m", "src.mcp_server.server"]
