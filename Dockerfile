FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2
WORKDIR /project
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml .
COPY src src
RUN --mount=type=secret,id=build_ca \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    python -m pip install --no-cache-dir .
COPY app app
COPY .streamlit .streamlit
COPY config config
COPY scripts scripts
COPY sql sql
RUN python -m scripts.run
EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=2)"
CMD ["python", "-m", "streamlit", "run", "app/Home.py", "--server.address=0.0.0.0", "--server.headless=true"]
