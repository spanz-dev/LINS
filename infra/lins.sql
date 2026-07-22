BEGIN;

DROP TABLE IF EXISTS public.motos CASCADE;

CREATE TABLE public.motos (
    id SERIAL PRIMARY KEY,
    marca TEXT NOT NULL,
    modelo TEXT NOT NULL,
    ano INTEGER NOT NULL,
    cilindrada INTEGER NOT NULL,
    quilometragem INTEGER NOT NULL,
    categoria TEXT NOT NULL,
    foto TEXT,
    fotos TEXT
);

ALTER SEQUENCE public.motos_id_seq RESTART WITH 8;

COMMIT;
