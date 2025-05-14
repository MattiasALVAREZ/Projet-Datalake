import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function GuessArtistGame() {
  const [artist, setArtist] = useState('');
  const [lyricsLines, setLyricsLines] = useState([]);
  const [currentLine, setCurrentLine] = useState('');
  const [input, setInput] = useState('');
  const [artistSuggestions, setArtistSuggestions] = useState([]);
  const [score, setScore] = useState({ attempts: 0, correct: 0, errors: 0 });
  const [gameOver, setGameOver] = useState(false);

  // Charger aléatoirement les paroles d'un seul artiste
  useEffect(() => {
    axios.get('http://localhost:8000/curated').then(response => {
      const { songs, artists } = response.data.curated_data;
      const groupedByArtist = {};

      // Grouper les chansons par artiste via artist_id
      songs.forEach(song => {
        const artistData = artists.find(artist => artist._id === song.artist_id);
        const artistName = artistData ? artistData.name : "Artiste inconnu";
        
        if (!groupedByArtist[artistName]) {
          groupedByArtist[artistName] = [];
        }

        const lines = song.lyrics.split('\n').filter(line => line.trim() !== '');
        groupedByArtist[artistName].push(...lines);
      });

      // Choisir un artiste aléatoire avec au moins 5 lignes
      const artistsWithLines = Object.entries(groupedByArtist).filter(([, lines]) => lines.length >= 5);
      if (artistsWithLines.length > 0) {
        const randomArtist = artistsWithLines[Math.floor(Math.random() * artistsWithLines.length)];
        const [artistName, lines] = randomArtist;

        setArtist(artistName);
        setLyricsLines(lines.sort(() => 0.5 - Math.random()).slice(0, 10));
        setCurrentLine(lines[Math.floor(Math.random() * lines.length)]);
      }
    }).catch(error => console.error("Erreur lors du chargement des paroles :", error));
  }, []);

  // Gestion des suggestions d'artistes
  const handleInputChange = (e) => {
    const query = e.target.value;
    setInput(query);
    if (query.length > 1) {
      axios.get('http://localhost:8000/curated').then(response => {
        const { artists } = response.data.curated_data;
        const allArtists = artists.map(artist => artist.name);
        const filtered = allArtists.filter(artist => artist.toLowerCase().includes(query.toLowerCase()));
        setArtistSuggestions(filtered.slice(0, 5));
      });
    } else {
      setArtistSuggestions([]);
    }
  };

  // Sélectionner une suggestion
  const handleSuggestionClick = (suggestion) => {
    setInput(suggestion);
    setArtistSuggestions([]);
  };

  // Afficher une nouvelle ligne
  const getNextLine = () => {
    if (lyricsLines.length > 0) {
      const nextLine = lyricsLines[Math.floor(Math.random() * lyricsLines.length)];
      setCurrentLine(nextLine);
    } else {
      setGameOver(true);
    }
  };

  // Vérifier la réponse
  const handleSubmit = () => {
    const isCorrect = input.trim().toLowerCase() === artist.toLowerCase();
    setScore((prev) => ({
      attempts: prev.attempts + 1,
      correct: prev.correct + (isCorrect ? 1 : 0),
      errors: prev.errors + (isCorrect ? 0 : 1)
    }));

    if (isCorrect) {
      setGameOver(true);
    } else {
      getNextLine();
    }
    setInput('');
  };

  // Passer à la ligne suivante (compte comme erreur)
  const handlePass = () => {
    setScore((prev) => ({
      attempts: prev.attempts + 1,
      errors: prev.errors + 1,
      correct: prev.correct
    }));
    getNextLine();
  };

  // Affichage de fin
  if (gameOver) {
    return (
      <div className="random-game-container">
        <h2>🎤 Retrouvez un artiste par ses titres</h2>
        <p>✅ Artiste correct : {artist}</p>
        <p>❌ Erreurs : {score.errors}</p>
        <button className="restart-button" onClick={() => window.location.reload()}>🔄 Rejouer</button>
      </div>
    );
  }

  return (
    <div className="random-game-container">
      <h2>🎤 Retrouvez un artiste par ses titres</h2>
      <h3>Dans ce jeu, vous devez retrouver l’artiste à partir d’un extrait d’une ligne de l’une de ses chansons. Si vous ne trouvez pas, vous pouvez passer à un autre extrait. Moins vous avez besoin d'extraits pour deviner, plus votre score sera élevé. Bonne chance !</h3>
      <div className="lyrics-excerpt">
        🎶 {currentLine}
      </div>
      <input
        type="text"
        className="artist-input"
        placeholder="Tapez le nom de l'artiste..."
        value={input}
        onChange={handleInputChange}
      />
      {artistSuggestions.length > 0 && (
        <ul className="artist-suggestions">
          {artistSuggestions.map((suggestion, index) => (
            <li key={index} className="suggestion-item" onClick={() => handleSuggestionClick(suggestion)}>
              {suggestion}
            </li>
          ))}
        </ul>
      )}
      <div>
        <button className="submit-button" onClick={handleSubmit}>✅ Valider</button>
        <button className="restart-button" onClick={handlePass} style={{ marginLeft: '10px' }}>⏭️ Passer</button>
      </div>
    </div>
  );
}
