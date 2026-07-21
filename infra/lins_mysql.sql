START TRANSACTION;

DROP TABLE IF EXISTS motos;

CREATE TABLE motos (
    id INT NOT NULL AUTO_INCREMENT,
    marca TEXT NOT NULL,
    modelo TEXT NOT NULL,
    ano INT NOT NULL,
    cilindrada INT NOT NULL,
    quilometragem INT NOT NULL,
    categoria TEXT NOT NULL,
    foto LONGTEXT,
    fotos LONGTEXT,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE motos AUTO_INCREMENT = 8;

COMMIT;
