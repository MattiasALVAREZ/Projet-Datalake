import pymysql
import pymongo
import os
from dotenv import load_dotenv
from random import seed, sample
from datetime import date
import sys
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import nltk
from nltk.corpus import stopwords
from pymongo import ReplaceOne

# Initialisation
load_dotenv(dotenv_path="/opt/airflow/.env")
seed(42)

# Télécharger les stopwords français si nécessaire
nltk.download("stopwords")
STOP_WORDS = set(stopwords.words("french"))

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

def fetch_data_for_artists(artists):
    """Récupère uniquement les données des artistes spécifiés depuis MySQL."""
    connection = create_mysql_connection()
    formatted_artists = ','.join(['%s'] * len(artists))

    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM artists WHERE name IN ({formatted_artists})", artists)
            artists_data = cursor.fetchall()

            cursor.execute(f"""
                SELECT s.*, a.name as artist_name
                FROM songs s 
                JOIN artists a ON s.artist_id = a.id 
                WHERE a.name IN ({formatted_artists})
            """, artists)

            songs_data = cursor.fetchall()

            return artists_data, songs_data
    finally:
        connection.close()

def process_artist_and_songs(artist, songs, mongo_db):
    """Prépare et insère les documents MongoDB pour l'artiste et ses chansons."""
    artist_doc = {
        "name": artist["name"],
        "bio": artist.get("bio", "Biographie non disponible"),
        "image_url": artist.get("image_url", ""),
    }

    artist_result = mongo_db.artists.find_one_and_update(
        {"name": artist_doc["name"]},
        {"$set": artist_doc},
        upsert=True,
        return_document=pymongo.ReturnDocument.AFTER
    )

    song_documents = []
    for song in songs:
        difficulty_versions = generate_difficulty_versions(song.get("lyrics", ""))
        song_doc = {
            "title": song["title"],
            "artist_id": artist_result["_id"],
            "url": song["url"],
            "image_url": song["image_url"],
            "language": song["language"],
            "release_date": str(song["release_date"]) if isinstance(song["release_date"], date) else song["release_date"],
            "pageviews": song["pageviews"],
            "lyrics": song.get("lyrics", ""),
            "french_lyrics": song.get("french_lyrics", ""),
            "difficulty_versions": difficulty_versions
        }
        song_documents.append(
            ReplaceOne(
                {"title": song["title"], "artist_id": artist_result["_id"]},
                song_doc,
                upsert=True
            )
        )

    if song_documents:
        mongo_db.songs.bulk_write(song_documents, ordered=False)
        print(f"Artiste : {artist['name']} | Chansons insérées : {len(song_documents)}")


def migrate_artists_to_mongodb(artists):
    """Migre uniquement les artistes spécifiés et leurs chansons vers MongoDB."""
    mongo_db = create_mongo_client()
    artists_data, songs_data = fetch_data_for_artists(artists)

    songs_by_artist = {}
    for song in songs_data:
        artist_name = song["artist_name"]
        if artist_name not in songs_by_artist:
            songs_by_artist[artist_name] = []
        songs_by_artist[artist_name].append(song)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {
            executor.submit(process_artist_and_songs, artist, songs_by_artist.get(artist["name"], []), mongo_db): artist["name"]
            for artist in artists_data
        }

        for future in as_completed(futures):
            artist_name = futures[future]
            try:
                future.result()
                print(f"Artiste traité : {artist_name}")
            except Exception as e:
                print(f"Erreur lors du traitement de l'artiste {artist_name} : {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python artists_staging_to_curated_fast.py <artist1> [<artist2> ...]")
        sys.exit(1)

    artists = sys.argv[1:]
    migrate_artists_to_mongodb(artists)
