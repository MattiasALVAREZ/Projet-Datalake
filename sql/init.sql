CREATE TABLE IF NOT EXISTS artists (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    bio TEXT,
    image_url VARCHAR(512),
    UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS songs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    artist_id INT,
    title VARCHAR(255) NOT NULL,
    url VARCHAR(512),
    image_url VARCHAR(512),
    language VARCHAR(10),
    release_date DATE,
    pageviews INT DEFAULT 0,
    lyrics TEXT,
    french_lyrics TEXT,
    FOREIGN KEY (artist_id) REFERENCES artists(id),
    UNIQUE(artist_id, title)
);
