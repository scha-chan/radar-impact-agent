FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY knowledge/ knowledge/

EXPOSE 8000

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Achado do card 26 (analise do log do job "build" da CI): pip avisava
# "Running pip as the 'root' user can result in broken permissions" - a
# imagem rodava como root por padrao. Cria um usuario sem privilegios para
# o processo da aplicacao; a instalacao de pacotes continua como root (a
# camada acima), so o CMD final roda sem privilegios.
#
# A limitacao de permissao de volume anotada no card 26 ("nada ainda
# escreve nesse caminho") deixou de ser hipotetica no card 30: o lifespan
# da API (src/api/app.py) cria o checkpoint sqlite na inicializacao, em
# /app/data (o volume montado por docker-compose.yml). "mkdir -p" + chown
# aqui, antes do USER trocar, garante que o usuario sem privilegios
# consegue escrever ali mesmo quando o volume nomeado do Docker e criado
# com dono root por padrao.
RUN useradd --create-home --shell /bin/bash radar \
    && mkdir -p /app/data \
    && chown -R radar:radar /app
USER radar

# Interface minima (card 30, RF-10) - `docker compose up` (RNF-06) usa
# este mesmo build. O servidor MCP (stdio, card 07) sobe separadamente
# via `python -m src.mcp_server.server`, nao faz sentido como CMD de um
# container de longa duracao (stdio espera um client conectado).
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
