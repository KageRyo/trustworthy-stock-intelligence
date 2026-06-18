FROM python:3.11-slim

WORKDIR /app
ENV PIP_NO_CACHE_DIR=1
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

COPY pyproject.toml README.md ./
COPY src ./src
COPY dashboard ./dashboard
COPY experiments/005_temporal_transformer_trust ./experiments/005_temporal_transformer_trust

RUN python -m pip install --upgrade pip && python -m pip install -e ".[dashboard]"

EXPOSE 8501
ENTRYPOINT ["streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
