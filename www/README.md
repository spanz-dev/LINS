# Projeto Enzo - Lins

Aplicacao Flask para loja/admin de motos.

## Estrutura

- `www/`: codigo da aplicacao Flask.
- `../infra/`: arquivos de infraestrutura Docker e dumps SQL.

## Rodar com Docker

Na pasta `infra`, execute:

```bash
docker compose up --build
```

A aplicacao ficara disponivel em:

```text
http://localhost:5001
```

O gerenciador web do banco ficara disponivel em:

```text
http://localhost:8080
```

Dados para acessar o PostgreSQL pelo Adminer:

```text
Sistema: PostgreSQL
Servidor: db
Usuario: enzo
Senha: enzo
Base de dados: enzo_lins
```

Para parar:

```bash
docker compose down
```

Para parar e apagar os dados do PostgreSQL local:

```bash
docker compose down -v
```

O PostgreSQL 18 usa o volume `postgres18_data` montado em `/var/lib/postgresql`.

## Importar SQL

Na pasta `infra`, execute:

```bash
docker compose up -d db adminer
docker compose exec -T db psql -U enzo -d enzo_lins -v ON_ERROR_STOP=1 < lins.sql
docker compose up -d web
```
