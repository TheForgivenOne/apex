FROM python:3.12-slim

WORKDIR /app

COPY ../setup.py ../README.md ./
COPY ../apex/ apex/
COPY app.py .

RUN pip install --no-cache-dir -e . && rm -rf /root/.cache

EXPOSE 8080

CMD ["python", "app.py"]
