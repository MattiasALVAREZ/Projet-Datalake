import requests
import boto3
import json
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from unidecode import unidecode
import sys
from concurrent.futures import ThreadPoolExecutor
from requests.adapters import HTTPAdapter, Retry

# Charger les variables d'environnement
load_dotenv(dotenv_path="/opt/airflow/.env")

GENIUS_ACCESS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
BUCKET_NAME = os.getenv("BUCKET_NAME")

# Base URL pour l'API Genius
BASE_URL = "https://api.genius.com"

# Sessions HTTP réutilisables avec gestion des retries
retries = Retry(
    total=5,  # Nombre maximal de tentatives
    backoff_factor=1,  # Délai exponentiel : 1s, 2s, 4s, 8s, 16s
    status_forcelist=[429, 500, 502, 503, 504],  # Erreurs à retenter
    allowed_methods=["GET"]  # Appliquer les retries uniquement aux requêtes GET
)

# Session pour l'API Genius
api_session = requests.Session()
api_session.headers.update({"Authorization": f"Bearer {GENIUS_ACCESS_TOKEN}"})
api_session.mount("https://", HTTPAdapter(max_retries=retries))

# Session pour le scraping des paroles
lyrics_session = requests.Session()
lyrics_session.mount("https://", HTTPAdapter(max_retries=retries))

# Client S3 réutilisé pour éviter les reconnections fréquentes
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

def request_genius(endpoint, params=None):
    """Effectue une requête à l'API Genius avec gestion des erreurs et des retries."""
    try:
        print(f"[API] Requête vers : {endpoint} avec paramètres : {params}")
        response = api_session.get(f"{BASE_URL}{endpoint}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la requête API : {e}")
        return None

def get_artist_id(artist_name):
    """Recherche l'ID d'un artiste sur Genius."""
    print(f"Recherche de l'ID pour l'artiste : {artist_name}")
    normalized_name = unidecode(artist_name.lower())
    data = request_genius("/search", {"q": normalized_name})
    if not data:
        return None

    for hit in data["response"]["hits"]:
        name = unidecode(hit["result"]["primary_artist"]["name"].lower())
        if name == normalized_name:
            artist_id = hit["result"]["primary_artist"]["id"]
            print(f"ID trouvé pour {artist_name} : {artist_id}")
            return artist_id

    print(f"Aucun match exact pour {artist_name}.")
    return None

def get_artist_details(artist_id):
    """Récupère les informations d'un artiste."""
    data = request_genius(f"/artists/{artist_id}")
    if not data:
        return None

    artist = data["response"]["artist"]
    bio_text = ""
    if "description" in artist and "dom" in artist["description"]:
        for item in artist["description"]["dom"].get("children", []):
            if isinstance(item, dict) and "children" in item:
                bio_text += "".join([c if isinstance(c, str) else "" for c in item["children"]])

    return {
        "name": artist["name"],
        "image_url": artist["image_url"],
        "bio": bio_text.strip(),
    }

def get_popular_songs_by_artist(artist_id):
    """Récupère jusqu'à 20 chansons où l'artiste est l'interprète principal."""
    data = request_genius(f"/artists/{artist_id}/songs", {"sort": "popularity", "per_page": 50})
    if not data:
        return []

    primary_songs = [song for song in data["response"]["songs"] if song["primary_artist"]["id"] == artist_id]
    return primary_songs[:20]

def get_song_lyrics(song_url):
    """Scrape les paroles d'une chanson depuis Genius avec retries."""
    try:
        print(f"Scraping des paroles depuis : {song_url}")
        response = lyrics_session.get(song_url, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        lyrics_divs = soup.find_all("div", {"data-lyrics-container": "true"})
        lyrics = "\n".join(div.get_text(separator="\n") for div in lyrics_divs)
        return lyrics.strip() if lyrics else "Paroles indisponibles"
    except Exception as e:
        print(f"Erreur lors du scraping des paroles : {e}")
        return "Paroles indisponibles"

def get_song_details(song_id):
    """Récupère les détails d'une chanson en incluant les paroles traduites si disponibles."""
    print(f"Récupération des détails pour la chanson ID : {song_id}")
    data = request_genius(f"/songs/{song_id}")
    if not data:
        return None

    song = data["response"]["song"]
    release_date = song.get("release_date_for_display", "unknown")

    details = {
        "title": song["title"],
        "url": song["url"],
        "image_url": song["song_art_image_url"],
        "language": song.get("language", "unknown"),
        "release_date": release_date,
        "pageviews": song["stats"].get("pageviews", 0),
        "lyrics": get_song_lyrics(song["url"]),
        "french_lyrics": "",  # Valeur par défaut si pas de traduction
    }

    # Récupération des paroles traduites si disponibles
    if details["language"] != "fr":
        french_translation = next(
            (t for t in song.get("translation_songs", []) if isinstance(t, dict) and str(t.get("language", "")).startswith("fr")),
            None
        )
        if french_translation and "url" in french_translation:
            translation_url = french_translation["url"]
            print(f"Récupération des paroles traduites depuis : {translation_url}")
            details["french_lyrics"] = get_song_lyrics(translation_url)
        else:
            print(f"Aucune traduction française disponible pour la chanson : {details['title']}")

    return details

def upload_to_s3(key, content):
    """Téléverse du contenu JSON sur S3 en évitant les doublons."""
    try:
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=json.dumps(content, ensure_ascii=False, indent=4).encode("utf-8"),
            ContentType="application/json",
        )
        print(f"Téléversement réussi : {key}")
    except Exception as e:
        print(f"Erreur lors du téléversement sur S3 : {str(e)}")

def process_artist(artist_name):
    artist_id = get_artist_id(artist_name)
    if not artist_id:
        return

    artist_details = get_artist_details(artist_id)
    songs = get_popular_songs_by_artist(artist_id)
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        song_details = list(executor.map(get_song_details, [song["id"] for song in songs]))

    artist_data = {
        "artist": artist_details,
        "songs": [s for s in song_details if s],
    }
    s3_key = f"raw/{unidecode(artist_name).replace(' ', '_').lower()}.json"
    upload_to_s3(s3_key, artist_data)

def process_artists(artists):
    max_workers = min(4, len(artists))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(process_artist, artists)
    print("Données enregistrées sur S3")

if __name__ == "__main__":
    artists = sys.argv[1:]
    process_artists(artists)
