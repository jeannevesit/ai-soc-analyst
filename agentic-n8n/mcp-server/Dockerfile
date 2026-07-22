FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

EXPOSE 8500

CMD ["python", "server.py", "--sse", "--host", "0.0.0.0", "--port", "8500"]
