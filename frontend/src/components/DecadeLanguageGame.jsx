import React, { useState, useEffect } from 'react';
import axios from 'axios';

export default function DecadeLanguageGame() {
  const [decade, setDecade] = useState('1970');
  const [language, setLanguage] = useState('fr');
  const [gameStarted, setGameStarted] = useState(false);
  const [songs, setSongs] = useState([]); // Chansons pour les extraits (filtrées)
  const [allSongs, setAllSongs] = useState([]); // Toutes les chansons de la base
  const [currentIndex, setCurrentIndex] = useState(0);
  const [currentLyrics, setCurrentLyrics] = useState([]);
  const [userInput, setUserInput] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [score, setScore] = useState(0);
  const [attempts, setAttempts] = useState(0);
  const [gameOver, setGameOver] = useState(false);

  // Charger toutes les chansons au démarrage
  useEffect(() => {
    axios.get('http://localhost:8000/curated').then(response => {
      const { songs, artists } = response.data.curated_data;
      
      // Associer chaque chanson à son artiste via artist_id
      const enrichedSongs = songs.map(song => {
        const artist = artists.find(a => a._id === song.artist_id);
        return {
          ...song,
          artistName: artist ? artist.name : "Artiste inconnu"
        };
      });

      setAllSongs(enrichedSongs); // Stocker toutes les chansons enrichies de la base
    }).catch(error => console.error('Erreur de récupération des données :', error));
  }, []);

  // Récupérer les chansons filtrées par décennie, langue, et avec une date de sortie valide
  const startGame = () => {
    const filteredSongs = allSongs.filter(song => {
      if (!song.release_date || song.release_date === "unknown") return false;
      const releaseYear = new Date(song.release_date).getFullYear();
      const decadeStart = parseInt(decade);
      return (
        releaseYear >= decadeStart &&
        releaseYear < decadeStart + 10 &&
        song.language === language
      );
    });

    const uniqueSongs = Array.from(new Set(filteredSongs.map(s => s.title)))
      .map(title => filteredSongs.find(song => song.title === title))
      .slice(0, 10); // Limiter à 10 pour les extraits

    setSongs(uniqueSongs);
    if (uniqueSongs.length > 0) {
      setCurrentLyrics(getRandomExcerpt(uniqueSongs[0].lyrics));
    }
    setCurrentIndex(0);
    setScore(0);
    setAttempts(0);
    setGameOver(false);
    setGameStarted(true);
  };

  // Extraire un bloc aléatoire de 5 lignes
  const getRandomExcerpt = (lyrics) => {
    const lines = lyrics.split('\n').filter(line => line.trim() !== '');
    if (lines.length === 0) return ['Aucune parole disponible.'];
    const startIndex = Math.max(0, Math.floor(Math.random() * Math.max(1, lines.length - 5)));
    return lines.slice(startIndex, startIndex + 5);
  };

  // Gérer la saisie de l'utilisateur et afficher les suggestions
  const handleInputChange = (e) => {
    const query = e.target.value;
    setUserInput(query);
    if (query.length > 1) {
      const matchingTitles = allSongs
        .map(song => song.title)
        .filter(title =>
          title.toLowerCase().includes(query.toLowerCase())
        );
      setSuggestions(matchingTitles.slice(0, 5));
    } else {
      setSuggestions([]);
    }
  };

  // Gérer la sélection d'une suggestion
  const handleSuggestionClick = (suggestion) => {
    setUserInput(suggestion);
    setSuggestions([]);
  };

  // Vérifier la réponse et passer à l'extrait suivant
  const handleSubmit = () => {
    if (songs.length === 0) return;

    const correctTitle = songs[currentIndex].title;
    setAttempts(attempts + 1);

    const isCorrect = userInput.toLowerCase() === correctTitle.toLowerCase();

    if (isCorrect) {
      setScore(score + 1);
      alert(`✅ Bonne réponse ! Le titre était bien "${correctTitle}".`);
    } else {
      alert(`❌ Mauvaise réponse. Le bon titre de l'extrait était : "${correctTitle}".`);
    }

    if (currentIndex < songs.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setCurrentLyrics(getRandomExcerpt(songs[currentIndex + 1].lyrics));
      setUserInput('');
    } else {
      setGameOver(true);
    }
  };

  // Passer à l'extrait suivant sans répondre
  const handlePass = () => {
    if (songs.length === 0) return;

    const correctTitle = songs[currentIndex].title;
    alert(`⏭️ Vous avez passé. Le bon titre était : "${correctTitle}".`);

    setAttempts(attempts + 1);
    if (currentIndex < songs.length - 1) {
      setCurrentIndex(currentIndex + 1);
      setCurrentLyrics(getRandomExcerpt(songs[currentIndex + 1].lyrics));
      setUserInput('');
    } else {
      setGameOver(true);
    }
  };

  return (
    <div className="random-game-container">
      {!gameStarted ? (
        <>
          <h2>📅 Retrouvez des titres par décennie et langue</h2>
          <h3>Dans ce jeu, vous choisissez une décennie et une langue, puis devez deviner le titre de chaque chanson aléatoire proposée (qui respectent vos critères de séléction). Chaque extrait est composé de 5 lignes de paroles tirées de la chanson. Une seule tentative par chanson. Bonne chance !</h3>
          <label>
            🕒 Décennie :
            <select value={decade} onChange={(e) => setDecade(e.target.value)}>
              <option value="1970">1970s</option>
              <option value="1980">1980s</option>
              <option value="1990">1990s</option>
              <option value="2000">2000s</option>
              <option value="2010">2010s</option>
              <option value="2020">2020s</option>
            </select>
          </label>
          <br />
          <label>
            🌐 Langue :
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="fr">Français</option>
              <option value="en">Anglais</option>
              <option value="es">Espagnol</option>
            </select>
          </label>
          <br />
          <button className="submit-button" onClick={startGame}>🎯 Jouer</button>
        </>
      ) : gameOver ? (
        <>
          <h2>🎉 Fin du jeu !</h2>
          <p>🎯 Score final : {score}/{songs.length}</p>
          <button className="restart-button" onClick={() => window.location.reload()}>🔄 Rejouer</button>
        </>
      ) : (
        <>
          <h2>📅 Retrouvez des titres par décennie et langue</h2>
          <div className="lyrics-excerpt">
            <p>🎶 Extrait de la chanson :</p>
            {currentLyrics.map((line, index) => (
              <p key={index}>{line}</p>
            ))}
          </div>
          <input
            type="text"
            className="artist-input"
            placeholder="Tapez le titre..."
            value={userInput}
            onChange={handleInputChange}
          />
          {suggestions.length > 0 && (
            <ul className="artist-suggestions">
              {suggestions.map((suggestion, index) => (
                <li key={index} onClick={() => handleSuggestionClick(suggestion)}>
                  {suggestion}
                </li>
              ))}
            </ul>
          )}
          <button className="submit-button" onClick={handleSubmit}>✅ Valider</button>
          <button className="restart-button" onClick={handlePass}>⏭️ Passer</button>
        </>
      )}
    </div>
  );
}
