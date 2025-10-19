#FROM python:3.9-slim

# Instala dependencias del sistema necesarias
#RUN apt-get update && apt-get install -y \
#    gcc \
#    libffi-dev \
#    libssl-dev \
#    build-essential \
#    zip \
#    && apt-get clean

# Establece el directorio de trabajo
#WORKDIR /app

# Copia los archivos
#COPY requirements.txt .

# Instala las dependencias
#RUN pip install --upgrade pip && pip install -r requirements.txt

# Copia el resto del proyecto
#COPY . .

# Expone el puerto
#EXPOSE 8000

# Comando para ejecutar FastAPI con Uvicorn
#CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM public.ecr.aws/lambda/python:3.9
WORKDIR /var/task
COPY requirements.txt .
RUN pip install -r requirements.txt --target .
COPY . .
CMD ["lambda_handler.handler"]
