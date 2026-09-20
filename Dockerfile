FROM python:3.10-slim

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY NotoKufiArabic-Regular.ttf ./
COPY . .

RUN mkdir -p /app/temp_storage

EXPOSE 8801

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8801"]