from flask import Flask, render_template, request, jsonify
import psycopg2
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")

UPLOAD_FOLDER = os.path.join(app.static_folder, "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024  # 6 MB por foto

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


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

    # Adiciona a coluna de foto sem quebrar bancos já existentes
    cursor.execute("""
        ALTER TABLE motos ADD COLUMN IF NOT EXISTS foto TEXT
    """)

    conexao.commit()
    cursor.close()
    conexao.close()


# Cria/atualiza a tabela assim que o app sobe (tanto local quanto no gunicorn)
criar_tabela()


def arquivo_permitido(nome_arquivo):
    return "." in nome_arquivo and nome_arquivo.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def salvar_foto(arquivo):
    """Salva o arquivo de foto no disco e devolve o nome salvo (ou None)."""
    if not arquivo or arquivo.filename == "":
        return None

    if not arquivo_permitido(arquivo.filename):
        raise ValueError("Formato de imagem não suportado. Use PNG, JPG, JPEG, WEBP ou GIF.")

    extensao = secure_filename(arquivo.filename).rsplit(".", 1)[1].lower()
    nome_salvo = f"{uuid.uuid4().hex}.{extensao}"
    arquivo.save(os.path.join(UPLOAD_FOLDER, nome_salvo))
    return nome_salvo


def moto_para_dict(moto):
    """moto = (id, marca, modelo, ano, cilindrada, quilometragem, categoria, foto)"""
    foto = moto[7]
    return {
        "id": moto[0],
        "marca": moto[1],
        "modelo": moto[2],
        "ano": moto[3],
        "cilindrada": moto[4],
        "quilometragem": moto[5],
        "categoria": moto[6],
        "foto": f"/static/uploads/{foto}" if foto else None
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
            nome_foto = salvar_foto(arquivo_foto)
        except ValueError as e:
            return jsonify({"ok": False, "erros": [str(e)]}), 400

        conexao = conectar_banco()
        cursor = conexao.cursor()

        cursor.execute("""
            INSERT INTO motos (marca, modelo, ano, cilindrada, quilometragem, categoria, foto)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, marca, modelo, ano, cilindrada, quilometragem, categoria, foto
        """, (marca, modelo, ano, cilindrada, quilometragem, categoria, nome_foto))

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

        cursor.execute("SELECT foto FROM motos WHERE id = %s", (moto_id,))
        registro = cursor.fetchone()

        cursor.execute("DELETE FROM motos WHERE id = %s", (moto_id,))

        if cursor.rowcount == 0:
            return jsonify({"ok": False, "erros": ["Moto não encontrada"]}), 404

        conexao.commit()

        # Remove a foto do disco, se existir
        if registro and registro[0]:
            caminho_foto = os.path.join(UPLOAD_FOLDER, registro[0])
            if os.path.exists(caminho_foto):
                os.remove(caminho_foto)

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
