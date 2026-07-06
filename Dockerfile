# استخدام صورة Python أساسية مع دعم OpenCV
FROM python:3.10-slim

# تثبيت المكتبات المطلوبة للنظام (مطلوبة لـ OpenCV و pyzbar)
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libzbar0 \
    && rm -rf /var/lib/apt/lists/*

# تحديد مجلد العمل
WORKDIR /app

# نسخ ملف المتطلبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ ملفات الخط العربي (إذا كان موجوداً)
# تأكد من وجود ملف NotoKufiArabic-Regular.ttf في نفس المجلد
COPY NotoKufiArabic-Regular.ttf ./

# نسخ باقي ملفات المشروع
COPY . .

# إنشاء مجلد مؤقت للتخزين
RUN mkdir -p /app/temp_storage

# تحديد المنفذ الذي سيعمل عليه التطبيق
EXPOSE 8801

# تشغيل التطبيق
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8801"]