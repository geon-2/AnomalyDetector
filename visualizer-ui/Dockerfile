FROM python:3.10-slim
WORKDIR /app
COPY app.py .
RUN pip install --no-cache-dir streamlit plotly pandas
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]