import { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import axios from "axios";

export default function ArtistList() {
  const [artists, setArtists] = useState([]);
  const [searchParams] = useSearchParams();
  const query = searchParams.get("search");

  useEffect(() => {
    if (query) {
      axios.get("http://localhost:8000/curated").then((response) => {
        const { artists } = response.data.curated_data;

        // Filtrer les artistes en fonction du query
        const filteredArtists = artists
          .filter((artist) =>
            artist.name.toLowerCase().includes(query.toLowerCase())
          )
          .map((artist) => ({
            name: artist.name,
            image_url: artist.image_url,
          }));

        setArtists(filteredArtists);
      }).catch((error) => {
        console.error("Erreur lors de la récupération des données :", error);
      });
    }
  }, [query]);

  return (
    <div className="list-container">
      <h2>Résultats pour "{query}"</h2>
      <ul className="artist-list">
        {artists.map((artist) => (
          <li key={artist.name} className="artist-item">
            <Link to={`/songs?search=${encodeURIComponent(artist.name)}`}>
              <img
                src={artist.image_url}
                alt={artist.name}
                className="artist-image"
              />
              {artist.name}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
