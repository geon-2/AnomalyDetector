FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install streamlit flask
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]