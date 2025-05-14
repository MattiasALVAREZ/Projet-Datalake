import { useState, useEffect } from "react";
import axios from "axios";

export default function RandomExtractGame() {
  const [allArtists, setAllArtists] = useState([]);
  const [artistInput, setArtistInput] = useState("");
  const [artistSuggestions, setArtistSuggestions] = useState([]);
  const [selectedArtist, setSelectedArtist] = useState("");
  const [gameStarted, setGameStarted] = useState(false);
  const [lyricsData, setLyricsData] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [score, setScore] = useState(0);
  const [userInput, setUserInput] = useState("");
  const [titleSuggestions, setTitleSuggestions] = useState([]);
  const [allTitles, setAllTitles] = useState([]);
  const [correctTitle, setCorrectTitle] = useState("");
  const [gameFinished, setGameFinished] = useState(false);

  // 🔍 Charger les données
  useEffect(() => {
    axios.get("http://localhost:8000/curated").then((response) => {
      const { songs, artists } = response.data.curated_data;
      const uniqueArtists = artists.map((artist) => artist.name);
      setAllArtists(uniqueArtists);

      const titles = songs.map((song) => song.title);
      setAllTitles(titles);
    });
  }, []);

  // 🔍 Suggestions d'artistes
  useEffect(() => {
    if (artistInput.length > 1) {
      const suggestions = allArtists.filter((artist) =>
        artist.toLowerCase().includes(artistInput.toLowerCase())
      );
      setArtistSuggestions(suggestions.slice(0, 5));
    } else {
      setArtistSuggestions([]);
    }
  }, [artistInput, allArtists]);

  // 🎯 Démarrer le jeu
  const startGame = (artist) => {
    setSelectedArtist(artist);
    setScore(0);
    setCurrentIndex(0);
    setGameFinished(false);

    axios.get("http://localhost:8000/curated").then((response) => {
      const { songs, artists } = response.data.curated_data;

      // Récupérer l'artiste correspondant
      const matchedArtist = artists.find((a) => a.name === artist);

      if (!matchedArtist) {
        alert("Artiste introuvable.");
        return;
      }

      // Filtrer les chansons associées à cet artiste via artist_id
      const allSongs = songs.filter(
        (song) => song.artist_id === matchedArtist._id
      );

      let randomExcerpts = [];
      let seenTitles = new Set();

      while (randomExcerpts.length < 10 && allSongs.length > 0) {
        const randomIndex = Math.floor(Math.random() * allSongs.length);
        const song = allSongs[randomIndex];
        if (!seenTitles.has(song.title)) {
          seenTitles.add(song.title);
          const lyrics = song.lyrics.split("\n");
          if (lyrics.length >= 5) {
            const randomLine = Math.floor(
              Math.random() * Math.max(lyrics.length - 5, 1)
            );
            const excerpt = lyrics
              .slice(randomLine, randomLine + 5)
              .join("\n");
            randomExcerpts.push({ excerpt, title: song.title });
          }
        }
      }

      if (randomExcerpts.length > 0) {
        setLyricsData(randomExcerpts);
        setCorrectTitle(randomExcerpts[0].title);
        setGameStarted(true);
        setArtistInput("");
        setArtistSuggestions([]);
      } else {
        alert("Aucune chanson disponible pour cet artiste.");
      }
    });
  };

  // 📚 Suggestions de titres
  useEffect(() => {
    if (userInput.length > 1) {
      const suggestions = allTitles.filter((title) =>
        title.toLowerCase().includes(userInput.toLowerCase())
      );
      setTitleSuggestions(suggestions.slice(0, 5));
    } else {
      setTitleSuggestions([]);
    }
  }, [userInput, allTitles]);

  // ✅ Vérifier la réponse
  const checkAnswer = () => {
    if (userInput.trim().toLowerCase() === correctTitle.toLowerCase()) {
      setScore((prev) => prev + 1);
    }

    if (currentIndex < lyricsData.length - 1) {
      const nextIndex = currentIndex + 1;
      setCurrentIndex(nextIndex);
      setCorrectTitle(lyricsData[nextIndex].title);
      setUserInput("");
      setTitleSuggestions([]);
    } else {
      setGameFinished(true);
      setGameStarted(false);
    }
  };

  // 🔁 Rejouer
  const resetGame = () => {
    setGameStarted(false);
    setLyricsData([]);
    setCurrentIndex(0);
    setScore(0);
    setUserInput("");
    setArtistInput("");
    setArtistSuggestions([]);
    setGameFinished(false);
  };

  return (
    <div className="random-game-container">
      {!gameStarted && !gameFinished ? (
        <div className="artist-selection">
          <h2>🎯 Retrouvez les titres d'un artiste</h2>
          <h3>Dans ce jeu, vous choisissez un artiste et devez deviner le titre de chaque extrait de chanson proposé. Un extrait est composé de 5 lignes de paroles tirées de la chanson. Une seule tentative par chanson. Bonne chance !</h3>
          <input
            type="text"
            value={artistInput}
            onChange={(e) => setArtistInput(e.target.value)}
            className="artist-input"
            placeholder="Entrez un artiste..."
          />
          <ul className="artist-suggestions">
            {artistSuggestions.map((artist, index) => (
              <li
                key={index}
                className="suggestion-item"
                onClick={() => startGame(artist)}
              >
                {artist}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {gameStarted && (
        <div className="game-play">
          {lyricsData.length > 0 && currentIndex < lyricsData.length && (
            <div className="question-block">
              <pre className="lyrics-excerpt">
                🎶 {lyricsData[currentIndex].excerpt}
              </pre>
              <input
                type="text"
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                className="title-input"
                placeholder="Tapez le titre de la chanson..."
              />
              <ul className="suggestions-list">
                {titleSuggestions.map((suggestion, index) => (
                  <li
                    key={index}
                    className="suggestion-item"
                    onClick={() => setUserInput(suggestion)}
                  >
                    {suggestion}
                  </li>
                ))}
              </ul>
              <button className="submit-button" onClick={checkAnswer}>
                ✅ Valider
              </button>
            </div>
          )}
        </div>
      )}

      {gameFinished && (
        <div className="result-screen">
          <h2>🎯 Fin du jeu !</h2>
          <p className="final-score">Votre score : {score}/10</p>
          <button className="restart-button" onClick={resetGame}>
            🔄 Rejouer
          </button>
        </div>
      )}
    </div>
  );
}
