FROM python:3.8-slim

# Installation des dépendances système, y compris le client MySQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    libssl-dev \
    default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail
WORKDIR /opt/api

# Copier les fichiers nécessaires
COPY . /opt/api

# Installer les dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Commande par défaut pour démarrer l'API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
