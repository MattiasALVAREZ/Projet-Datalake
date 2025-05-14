import { BrowserRouter as Router, Route, Routes } from "react-router-dom";
import Home from "./components/Home";
import ArtistList from "./components/ArtistList";
import SongDetails from "./components/SongDetails";
import ResultPage from "./components/ResultPage";
import ArtistPage from "./components/ArtistPage";
import RandomExtractGame from "./components/RandomExtractGame";
import GuessArtist from "./components/GuessArtist";
import DecadeLanguageGame from "./components/DecadeLanguageGame";
import MysteryTranslationGame from "./components/MysteryTranslationGame";

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/artists" element={<ArtistList />} />
        <Route path="/song/:title" element={<SongDetails />} />
        <Route path="/result" element={<ResultPage />} />
        <Route path="/artist/:artistName" element={<ArtistPage />} />
        <Route path="/random-game" element={<RandomExtractGame />} />
        <Route path="/guess-artist" element={<GuessArtist />} />
        <Route path="/game/decade-language" element={<DecadeLanguageGame />} />
        <Route path="/game/translation-game" element={<MysteryTranslationGame />} />
      </Routes>
    </Router>
  );
}
