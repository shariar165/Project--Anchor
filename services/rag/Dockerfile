FROM python:3.12-slim

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the fastembed model into an image layer so it isn't downloaded (and
# re-spiking RAM) on every restart — Railway has no persistent volume.
ENV FASTEMBED_CACHE_PATH=/code/.fastembed_cache
ENV EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
RUN python -c "from fastembed import TextEmbedding; import os; TextEmbedding(os.environ['EMBEDDING_MODEL'], cache_dir=os.environ['FASTEMBED_CACHE_PATH'])"

COPY . .

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}
