import pymysql
import pymongo
import os
from dotenv import load_dotenv
from random import seed
from datetime import date
import sys
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import nltk
from nltk.corpus import stopwords
from pymongo import ReplaceOne

# Initialisation
seed(42)
nltk.download("stopwords")
STOP_WORDS = set(stopwords.words("french"))

# Charger les variables d'environnement
load_dotenv(dotenv_path="/opt/airflow/.env")

# Configuration MySQL
MYSQL_HOST = os.getenv("MYSQL_HOST")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))

# Configuration MongoDB
MONGO_URI = "mongodb://mongodb-dlk:27017/"
MONGO_DATABASE = "datalakes_curated"

def create_mysql_connection():
    """Crée une nouvelle connexion MySQL pour chaque thread."""
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        port=MYSQL_PORT,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )

def create_mongo_client():
    """Crée une nouvelle connexion MongoDB pour chaque thread."""
    return pymongo.MongoClient(MONGO_URI)[MONGO_DATABASE]

def mask_words(line, percentage, stop_words):
    """Masque un pourcentage de mots dans une ligne de texte."""
    words = line.split()
    maskable_indices = [i for i, w in enumerate(words) if w.lower() not in stop_words]
    num_to_mask = max(1, int(len(maskable_indices) * percentage / 100)) if maskable_indices else 0
    mask_indices = np.random.choice(maskable_indices, min(len(maskable_indices), num_to_mask), replace=False)
    return " ".join("____" if i in mask_indices else word for i, word in enumerate(words))

def generate_difficulty_versions(lyrics, easy_pct=10, medium_pct=25, hard_pct=40):
    """Génère trois versions de paroles en masquant un pourcentage de mots."""
    if not lyrics:
        return {"easy": "Paroles indisponibles", "medium": "Paroles indisponibles", "hard": "Paroles indisponibles"}

    return {
        "easy": "\n".join(mask_words(line, easy_pct, STOP_WORDS) for line in lyrics.splitlines()),
        "medium": "\n".join(mask_words(line, medium_pct, STOP_WORDS) for line in lyrics.splitlines()),
        "hard": "\n".join(mask_words(line, hard_pct, STOP_WORDS) for line in lyrics.splitlines()),
    }

def fetch_songs_from_mysql(songs: list):
    """Récupère uniquement les chansons spécifiées depuis MySQL."""
    connection = create_mysql_connection()
    try:
        with connection.cursor() as cursor:
            formatted_titles = ','.join(['%s'] * len(songs))
            query = f"""
                SELECT songs.*, artists.name AS artist_name, artists.bio AS artist_bio, artists.image_url AS artist_image_url
                FROM songs 
                LEFT JOIN artists ON songs.artist_id = artists.id
                WHERE CONCAT(artists.name, ' - ', songs.title) IN ({formatted_titles})
            """
            formatted_songs = [f"{song['artist']} - {song['title']}" for song in songs]
            cursor.execute(query, formatted_songs)
            return cursor.fetchall()
    finally:
        connection.close()

def process_song(song, mongo_db):
    """Prépare et insère le document MongoDB pour une chanson spécifique."""
    difficulty_versions = generate_difficulty_versions(song.get("lyrics", ""))

    artist_doc = {
        "name": song["artist_name"],
        "bio": song.get("artist_bio", "Biographie non disponible"),
        "image_url": song.get("artist_image_url", ""),
    }

    # Insertion ou mise à jour de l'artiste dans MongoDB
    artist_result = mongo_db.artists.find_one_and_update(
        {"name": artist_doc["name"]},
        {"$set": artist_doc},
        upsert=True,
        return_document=pymongo.ReturnDocument.AFTER
    )

    # Préparation du document de la chanson pour MongoDB
    song_doc = {
        "title": song["title"],
        "artist_id": artist_result["_id"],
        "url": song["url"],
        "image_url": song["image_url"],
        "language": song["language"],
        "release_date": str(song["release_date"]) if isinstance(song["release_date"], date) else song["release_date"],
        "pageviews": song["pageviews"],
        "lyrics": song.get("lyrics", ""),
        "difficulty_versions": difficulty_versions,
        "french_lyrics": song.get("french_lyrics", ""),
    }

    return song_doc

def migrate_songs_to_mongodb(songs: list):
    """Migre uniquement les chansons spécifiées vers MongoDB avec optimisation."""
    mongo_db = create_mongo_client()
    songs_data = fetch_songs_from_mysql(songs)

    documents = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_song, song, mongo_db): song for song in songs_data}

        for future in as_completed(futures):
            result = future.result()
            if result:
                documents.append(result)

    if documents:
        try:
            bulk_operations = [
                ReplaceOne(
                    {"title": doc["title"], "artist_id": doc["artist_id"]},
                    doc,
                    upsert=True
                ) for doc in documents
            ]
            result = mongo_db.songs.bulk_write(bulk_operations, ordered=False)
            print(f"MongoDB : {len(documents)} chansons (insertées : {result.upserted_count}, mises à jour : {result.modified_count})")
        except Exception as e:
            print(f"Erreur lors de l'insertion dans MongoDB : {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3 or len(sys.argv) % 2 == 0:
        print("Usage : python songs_staging_to_curated_fast.py <title1> <artist1> [<title2> <artist2> ...]")
        sys.exit(1)

    songs = [{"title": sys.argv[i], "artist": sys.argv[i + 1]} for i in range(1, len(sys.argv), 2)]
    migrate_songs_to_mongodb(songs)
