import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";

export default function ArtistPage() {
  const { artistName } = useParams();
  const [artist, setArtist] = useState(null);

  useEffect(() => {
    axios
      .get("http://localhost:8000/curated")
      .then((response) => {
        const { songs, artists } = response.data.curated_data;

        // Trouver l'artiste dans la collection artists
        const matchedArtist = artists.find(
          (artist) => artist.name === artistName
        );

        if (matchedArtist) {
          // Récupérer les chansons associées à cet artiste via artist_id
          const artistSongs = songs
            .filter((song) => song.artist_id === matchedArtist._id)
            .map((song) => ({
              title: song.title,
              release_date: song.release_date,
              image_url: song.image_url,
            }));

          const artistInfo = {
            name: matchedArtist.name,
            bio: matchedArtist.bio,
            image_url: matchedArtist.image_url,
            songs: artistSongs,
          };

          setArtist(artistInfo);
        }
      })
      .catch((error) =>
        console.error("Erreur de récupération des données :", error)
      );
  }, [artistName]);

  if (!artist) return <div>Chargement...</div>;

  return (
    <div className="artist-container">
      {/* En-tête avec nom et photo */}
      <div className="artist-header">
        <img
          src={artist.image_url}
          alt={artist.name}
          className="artist-image"
        />
        <div className="artist-info">
          <h2>{artist.name}</h2>
        </div>
      </div>

      {/* Liste des chansons avec le même style que sur Home.jsx */}
      <ul className="result-list">
        {artist.songs.map((song, index) => (
          <li key={index} className="song-item">
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
      </ul>
    </div>
  );
}
