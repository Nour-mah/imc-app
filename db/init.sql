CREATE TABLE IF NOT EXISTS mesures (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    poids         DECIMAL(5, 2) NOT NULL,
    taille        DECIMAL(4, 2) NOT NULL,
    imc           DECIMAL(5, 2) NOT NULL,
    categorie     VARCHAR(50)   NOT NULL,
    date_creation TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
