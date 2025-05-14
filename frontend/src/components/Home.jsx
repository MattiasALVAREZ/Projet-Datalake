import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";

export default function Home() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    if (query.length > 2) {
      axios
        .get("http://localhost:8000/curated")
        .then((response) => {
          const { songs, artists } = response.data.curated_data;

          // Création d'un dictionnaire {artist_id: artist_data} pour un accès rapide
          const artistMap = artists.reduce((acc, artist) => {
            acc[artist._id] = artist;
            return acc;
          }, {});

          // Associer les artistes aux chansons en utilisant artist_id
          const enrichedSongs = songs.map((song) => ({
            ...song,
            artist: artistMap[song.artist_id] || {
              name: "Artiste inconnu",
              image_url: "",
              bio: "Biographie non disponible",
            },
          }));

          // Filtrer par titre ou nom d'artiste
          const filteredResults = enrichedSongs.filter(
            (song) =>
              song.title.toLowerCase().includes(query.toLowerCase()) ||
              song.artist.name.toLowerCase().includes(query.toLowerCase())
          );

          setResults(filteredResults);
        })
        .catch((error) => {
          console.error("Erreur lors de la récupération des données :", error);
        });
    } else {
      setResults([]);
    }
  }, [query]);

  // Regrouper les chansons par artiste
  const groupedSongs = results.reduce((acc, song) => {
    const artistName = song.artist.name;
    if (!acc[artistName]) {
      acc[artistName] = {
        artistName: artistName,
        artistImage: song.artist.image_url,
        songs: [],
      };
    }
    acc[artistName].songs.push(song);
    return acc;
  }, {});

  // Vérifier si le query correspond au nom d'un artiste
  const isArtistQuery =
    query.length > 2 &&
    Object.values(groupedSongs).some((group) =>
      group.artistName.toLowerCase().includes(query.toLowerCase())
    );

  return (
    <div className="home-container">
      <h1 className="title">🎵 Lyrics Challenge 🎵</h1>
      <p className="subtitle">Testez vos connaissances en paroles de chansons !</p>

      <div className="search-container">
        <input
          type="text"
          placeholder="🔍 Rechercher une chanson ou un artiste..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="styled-search-bar"
        />
      </div>

      <div className="button-container">
        <button
          className="home-button"
          onClick={() => navigate("/random-game")}
        >
          🎯 Jeu 1 : Retrouvez les titres d'un artiste
        </button>
        <button
          className="home-button"
          onClick={() => navigate("/guess-artist")}
        >
          🎤 Jeu 2 : Retrouvez un artiste par ses titres
        </button>
        <button
          className="home-button"
          onClick={() => navigate("/game/decade-language")}
        >
          📅 Jeu 3 : Retrouvez des titres par décennie et langue
        </button>
        <button className="home-button"
        onClick={() => navigate("/game/translation-game")}
        >🌍 Jeu 4 : Retrouvez un titre grâce à sa traduction</button>
      </div>

      <ul className="result-list">
        {Object.values(groupedSongs).map((group, index) => (
          <div key={index}>
            {/* Affiche l'artiste uniquement si la recherche correspond à un artiste */}
            {isArtistQuery && (
              <li className="artist-item">
                <img
                  src={group.artistImage}
                  alt={group.artistName}
                  className="song-image-right"
                />
                <Link
                  to={`/artist/${encodeURIComponent(group.artistName)}`}
                  className="song-link"
                >
                  🎤 {group.artistName}
                </Link>
              </li>
            )}

            {/* Afficher les chansons dans tous les cas */}
            {group.songs.map((song, idx) => (
              <li key={`${song.title}-${idx}`} className="song-item">
                <div className="song-info">
                  <Link
                    to={`/song/${encodeURIComponent(song.title)}`}
                    className="song-link"
                  >
                    {song.title}
                  </Link>
                </div>
                <img
                  src={song.image_url}
                  alt={song.title}
                  className="song-image-right"
                />
              </li>
            ))}
          </div>
        ))}
      </ul>
    </div>
  );
}
