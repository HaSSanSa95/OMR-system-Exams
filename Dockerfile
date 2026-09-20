FROM python:3.10-slim

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

# استخدام الفاصلة المنقوطة (;) يمنع تحويل & إلى &amp; نهائياً
RUN apt-get clean ; apt-get update --fix-missing ; apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libzbar0 \
    libzbar-dev \
    fonts-amiri \
    libfribidi-dev \
    libharfbuzz-dev \
    ; rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY NotoKufiArabic-Regular.ttf ./
COPY . .

RUN mkdir -p /app/temp_storage

EXPOSE 8801

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8801"]