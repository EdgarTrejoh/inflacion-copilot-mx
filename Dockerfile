# Usamos una imagen ligera de Python 3.12
FROM python:3.12-slim

# Evita que Python genere archivos .pyc y permite ver logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Establecemos el directorio de trabajo
WORKDIR /app

# Instalamos dependencias del sistema necesarias para BigQuery y Pandas
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiamos el archivo de requisitos e instalamos las librerías
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo el código de la app al contenedor
COPY . .

# Exponemos el puerto 8080 (el estándar de Cloud Run)
EXPOSE 8080

# Comando para arrancar Streamlit con las configuraciones de seguridad necesarias
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]