# Règlement de comptes : image de l'API Python (moteur, témoins, agents, greffier)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    RDC_DATA_DIR=/data

RUN useradd --create-home --uid 1000 app
WORKDIR /app

# Les dépendances d'abord : cette couche reste en cache tant que requirements.txt ne change pas
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app backend ./backend
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/profils')" || exit 1

# Un seul processus : les procès Bedrock (~30 s) tournent dans les fils de FastAPI.
CMD ["uvicorn", "api:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
