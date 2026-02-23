# On part d'une base Python légère
FROM python:3.10-slim

# On installe les outils nécessaires pour compiler Zvec (C++)
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    && rm -rf /var/lib/apt/lists/*

# On crée le dossier de travail dans le conteneur
WORKDIR /app

# On copie les fichiers de ton PC vers le conteneur
COPY requirements.txt .
COPY bot.py .

# On installe les librairies Python
RUN pip install --no-cache-dir -r requirements.txt

# On crée un dossier pour la base de données (volume)
RUN mkdir -p /data/zvec_db

# La commande qui lance le bot
CMD ["python", "bot.py"]