FROM python:3.9-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    flask==3.0.0 \
    flask-cors==4.0.0 \
    streamlit==1.28.0 \
    pandas==2.0.3

COPY main.py .
COPY dashboard.py .

EXPOSE 8502 8501

CMD ["sh", "-c", "python -u main.py & sleep 3 && streamlit run dashboard.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true"]
