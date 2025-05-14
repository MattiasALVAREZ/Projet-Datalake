import { useLocation, useNavigate } from "react-router-dom";

export default function ResultPage() {
  const { state } = useLocation();
  const { userAnswers, song, difficulty } = state;
  const navigate = useNavigate();

  const originalLyrics = song.lyrics.split(/\s+/);
  const maskedLyrics = song.difficulty_versions[difficulty].split("\n");

  let missingWords = [];
  let originalWordIndex = 0;

  maskedLyrics.forEach((line) => {
    line.split(" ").forEach((word) => {
      if (word === "____" && originalWordIndex < originalLyrics.length) {
        missingWords.push(
          originalLyrics[originalWordIndex].replace(/[,.;!?]/g, "")
        );
      }
      originalWordIndex++;
    });
  });

  let correctWords = 0;
  let wordIndex = 0;

  const correctedLyrics = maskedLyrics.map((line, index) => (
    <p key={index} className="lyrics-line">
      {line.split(" ").map((word, i) => {
        if (word === "____") {
          const userInput = (userAnswers[`${index}-${i}`] || "").replace(
            /[,.;!?]/g,
            ""
          );
          const correctWord = (missingWords[wordIndex] || "").replace(
            /[,.;!?]/g,
            ""
          );
          wordIndex++;

          const normalizedUserInput = userInput.trim().toLowerCase();
          const normalizedCorrectWord = correctWord.trim().toLowerCase();

          if (normalizedUserInput === normalizedCorrectWord) {
            correctWords++;
            return (
              <span key={i}>
                <input
                  type="text"
                  value={correctWord}
                  readOnly
                  className="word-input correct"
                />
              </span>
            );
          } else {
            return (
              <span key={i} className="incorrect-word">
                {userInput ? (
                  <del
                    className="incorrect-answer"
                    style={{ width: `${Math.max(6, userInput.length)}ch` }}
                  >
                    {userInput}
                  </del>
                ) : (
                  <span className="incorrect-answer">____</span>
                )}
                <span
                  className="correct-hint"
                  style={{ color: "green", marginLeft: "5px" }}
                >
                  ({correctWord})
                </span>
              </span>
            );
          }
        } else {
          return <span key={i}>{word} </span>;
        }
      })}
    </p>
  ));

  const score =
    missingWords.length > 0
      ? Math.round((correctWords / missingWords.length) * 100)
      : 0;

  return (
    <div className="song-container">
      <div className="song-header">
        <img src={song.image_url} alt={song.title} className="song-image" />
        <div className="song-info">
          <h2 className="song-title">
            {song.title} - {song.artist.name}
          </h2>
          <p className="release-date">
            📅 Sortie :{" "}
            {song.release_date !== "unknown"
              ? new Date(song.release_date).toLocaleDateString("fr-FR")
              : "Date inconnue"}
          </p>
        </div>
      </div>

      <h2 className="result-score">🎯 Résultat : {score}% correct</h2>

      <div className="lyrics-container">{correctedLyrics}</div>

      <button className="finish-button" onClick={() => navigate("/")}>
        Rejouer
      </button>
    </div>
  );
}
