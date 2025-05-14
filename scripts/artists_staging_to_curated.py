import pymysql
import pymongo
import os
from dotenv import load_dotenv
from random import seed, sample
from datetime import date
import sys
from nltk.corpus import stopwords
import nltk
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

# Connexion à MySQL
mysql_connection = pymysql.connect(
    host=MYSQL_HOST,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE,
    port=MYSQL_PORT,
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

# Connexion à MongoDB
mongo_client = pymongo.MongoClient(MONGO_URI)
mongo_db = mongo_client[MONGO_DATABASE]


def generate_difficulty_versions(lyrics, easy_pct=10, medium_pct=25, hard_pct=40):
    if not lyrics:
        return {"easy": "Paroles indisponibles", "medium": "Paroles indisponibles", "hard": "Paroles indisponibles"}

    def mask_words(line, percentage):
        words = line.split()
        maskable_indices = [i for i, w in enumerate(words) if w.lower() not in STOP_WORDS]
        num_to_mask = max(1, int(len(maskable_indices) * percentage / 100)) if maskable_indices else 0
        mask_indices = sample(maskable_indices, min(len(maskable_indices), num_to_mask))
        return " ".join("____" if i in mask_indices else word for i, word in enumerate(words))

    easy = "\n".join(mask_words(line, easy_pct) for line in lyrics.splitlines())
    medium = "\n".join(mask_words(line, medium_pct) for line in lyrics.splitlines())
    hard = "\n".join(mask_words(line, hard_pct) for line in lyrics.splitlines())

    return {"easy": easy, "medium": medium, "hard": hard}


def migrate_to_mongodb(artists):
    with mysql_connection.cursor() as cursor:
        formatted_artists = ','.join(['%s'] * len(artists))
        cursor.execute(f"SELECT * FROM artists WHERE name IN ({formatted_artists})", artists)
        artists_data = cursor.fetchall()

        if not artists_data:
            print("Aucun artiste correspondant trouvé dans MySQL.")
            return

        # Insertion ou mise à jour des artistes dans MongoDB
        artist_operations = []
        for artist in artists_data:
            artist_doc = {
                "name": artist["name"],
                "bio": artist.get("bio", "Biographie non disponible"),
                "image_url": artist.get("image_url", ""),
            }
            artist_operations.append(
                ReplaceOne(
                    {"name": artist_doc["name"]},
                    artist_doc,
                    upsert=True
                )
            )

        if artist_operations:
            mongo_db.artists.bulk_write(artist_operations, ordered=False)
            print(f"Artistes insérés ou mis à jour : {len(artist_operations)}")

        # Récupération des chansons liées aux artistes
        artist_ids = [artist["id"] for artist in artists_data]
        cursor.execute(f"SELECT * FROM songs WHERE artist_id IN ({','.join(map(str, artist_ids))})")
        songs = cursor.fetchall()

        song_operations = []
        for song in songs:
            artist = next((a for a in artists_data if a["id"] == song["artist_id"]), None)
            if not artist:
                continue

            # Récupérer l'ID de l'artiste depuis MongoDB
            artist_mongo = mongo_db.artists.find_one({"name": artist["name"]})
            if not artist_mongo:
                continue

            lyrics = song.get("lyrics", "")
            french_lyrics = song.get("french_lyrics", "")
            difficulty_versions = generate_difficulty_versions(lyrics)

            song_doc = {
                "title": song["title"],
                "artist_id": artist_mongo["_id"],
                "url": song["url"],
                "image_url": song["image_url"],
                "language": song["language"],
                "release_date": str(song["release_date"]) if isinstance(song["release_date"], date) else song["release_date"],
                "pageviews": song["pageviews"],
                "lyrics": lyrics,
                "difficulty_versions": difficulty_versions,
                "french_lyrics": french_lyrics if french_lyrics else ""
            }

            song_operations.append(
                ReplaceOne(
                    {"title": song["title"], "artist_id": artist_mongo["_id"]},
                    song_doc,
                    upsert=True
                )
            )

        if song_operations:
            mongo_db.songs.bulk_write(song_operations, ordered=False)
            print(f"Chansons insérées ou mises à jour : {len(song_operations)}")

    print("Migration complète vers MongoDB !")


if __name__ == "__main__":
    artists = sys.argv[1:]
    migrate_to_mongodb(artists)
