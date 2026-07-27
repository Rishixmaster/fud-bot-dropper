FROM python:3.12-slim

WORKDIR /app

# सर्व फाइल्स copy करा
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "bot.py"]
