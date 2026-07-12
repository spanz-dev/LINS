from flask import Flask, render_template, request, jsonify
import psycopg2
import os
import base64

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

ALLOWED_MIMETYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024  # 6 MB por foto


def conectar_banco():
    return psycopg2.connect(DATABASE_URL)


def criar_tabela():
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS motos (
            id SERIAL PRIMARY KEY,
            marca TEXT NOT NULL,
            modelo TEXT NOT NULL,
            ano TEXT NOT NULL,
            cilindrada TEXT NOT NULL,
            quilometragem TEXT NOT NULL,
            categoria TEXT NOT NULL
        )
    """)

    # A foto fica salva como base64 direto na coluna (texto), então não depende
    # do disco do servidor — no Render (e na maioria dos PaaS grátis) o disco é
    # apagado a cada reinício/deploy, então guardar só o caminho do arquivo
    # fazia a imagem "sumir" com o tempo. Guardando no Postgres, ela persiste.
    cursor.execute("""
        ALTER TABLE motos ADD COLUMN IF NOT EXISTS foto TEXT
    """)

    conexao.commit()
    cursor.close()
    conexao.close()


# Cria/atualiza a tabela assim que o app sobe (tanto local quanto no gunicorn)
criar_tabela()


def codificar_foto(arquivo):
    """Lê o arquivo enviado e devolve uma data URI base64 (ou None)."""
    if not arquivo or arquivo.filename == "":
        return None

    if arquivo.mimetype not in ALLOWED_MIMETYPES:
        raise ValueError("Formato de imagem não suportado. Use PNG, JPG, JPEG, WEBP ou GIF.")

    conteudo = arquivo.read()
    base64_str = base64.b64encode(conteudo).decode("utf-8")
    return f"data:{arquivo.mimetype};base64,{base64_str}"


def moto_para_dict(moto):
    """moto = (id, marca, modelo, ano, cilindrada, quilometragem, categoria, foto)"""
    return {
        "id": moto[0],
        "marca": moto[1],
        "modelo": moto[2],
        "ano": moto[3],
        "cilindrada": moto[4],
        "quilometragem": moto[5],
        "categoria": moto[6],
        "foto": moto[7]  # já é a data URI base64 pronta pra usar em <img src="">
    }


# ---------------- PÁGINAS ----------------

@app.route('/')
def html():
    return render_template("index.html")


@app.route('/moto.html')
def pagina_detalhe():
    return render_template("moto.html")


@app.route('/adicionar.html')
def pagina_adicionar():
    return render_template("adicionar.html")


# ---------------- API ----------------

@app.route('/api/motos', methods=['POST'])
def api_motos():
    marca = request.form.get('marca')
    modelo = request.form.get('modelo')
    ano = request.form.get('ano')
    cilindrada = request.form.get('cilindrada')
    quilometragem = request.form.get('quilometragem')
    categoria = request.form.get('categoria')
    arquivo_foto = request.files.get('foto')

    if not all([marca, modelo, ano, cilindrada, quilometragem, categoria]):
        return jsonify({"ok": False, "erros": ["Preencha todos os campos"]}), 400

    conexao = None
    cursor = None
    try:
        try:
            foto_base64 = codificar_foto(arquivo_foto)
        except ValueError as e:
            return jsonify({"ok": False, "erros": [str(e)]}), 400

        conexao = conectar_banco()
        cursor = conexao.cursor()

        cursor.execute("""
            INSERT INTO motos (marca, modelo, ano, cilindrada, quilometragem, categoria, foto)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, marca, modelo, ano, cilindrada, quilometragem, categoria, foto
        """, (marca, modelo, ano, cilindrada, quilometragem, categoria, foto_base64))

        nova_moto = cursor.fetchone()
        conexao.commit()

        return jsonify({"ok": True, "mensagem": "Moto cadastrada com sucesso", "moto": moto_para_dict(nova_moto)})

    except psycopg2.errors.UniqueViolation:
        return jsonify({"ok": False, "erros": ["Moto já cadastrada"]}), 400

    except Exception as e:
        return jsonify({"ok": False, "erros": [str(e)]}), 500

    finally:
        if cursor:
            cursor.close()
        if conexao:
            conexao.close()


@app.route("/api/motos_cadastradas", methods=["GET"])
def listar_motos():
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, marca, modelo, ano, cilindrada, quilometragem, categoria, foto
        FROM motos
        ORDER BY id DESC
    """)

    motos = cursor.fetchall()

    cursor.close()
    conexao.close()

    return jsonify([moto_para_dict(m) for m in motos])


@app.route("/api/motos/<int:moto_id>", methods=["GET"])
def obter_moto(moto_id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, marca, modelo, ano, cilindrada, quilometragem, categoria, foto
        FROM motos
        WHERE id = %s
    """, (moto_id,))

    moto = cursor.fetchone()

    cursor.close()
    conexao.close()

    if not moto:
        return jsonify({"ok": False, "erros": ["Moto não encontrada"]}), 404

    return jsonify(moto_para_dict(moto))


@app.route("/api/motos/<int:moto_id>", methods=["DELETE"])
def deletar_moto(moto_id):
    conexao = None
    cursor = None
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()

        cursor.execute("DELETE FROM motos WHERE id = %s", (moto_id,))

        if cursor.rowcount == 0:
            return jsonify({"ok": False, "erros": ["Moto não encontrada"]}), 404

        conexao.commit()

        return jsonify({"ok": True, "mensagem": "Moto removida com sucesso"})

    except Exception as e:
        return jsonify({"ok": False, "erros": [str(e)]}), 500

    finally:
        if cursor:
            cursor.close()
        if conexao:
            conexao.close()


if __name__ == '__main__':
    app.run(debug=True)
