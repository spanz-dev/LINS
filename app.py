from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from functools import wraps
import psycopg2
import os
import base64
import json

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")

DATABASE_URL = os.getenv("DATABASE_URL")

USUARIO_ADMIN = "admin"
SENHA_ADMIN = "1702"

ALLOWED_MIMETYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}

app.config["MAX_CONTENT_LENGTH"] = 35 * 1024 * 1024  # 35 MB por requisição


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

   
    cursor.execute("ALTER TABLE motos ADD COLUMN IF NOT EXISTS fotos TEXT")


    cursor.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'motos' AND column_name = 'foto'
    """)
    tem_coluna_antiga = cursor.fetchone() is not None

    if tem_coluna_antiga:
        cursor.execute("SELECT id, foto FROM motos WHERE foto IS NOT NULL AND fotos IS NULL")
        antigas = cursor.fetchall()
        for moto_id, foto in antigas:
            cursor.execute(
                "UPDATE motos SET fotos = %s WHERE id = %s",
                (json.dumps([foto]), moto_id)
            )

    conexao.commit()
    cursor.close()
    conexao.close()



criar_tabela()


def login_obrigatorio(f):
    """Protege páginas do painel: se não estiver logado, manda pro login."""
    @wraps(f)
    def decorada(*args, **kwargs):
        if not session.get('logado'):
            return redirect(url_for('pagina_login'))
        return f(*args, **kwargs)
    return decorada


def login_obrigatorio_api(f):
    """Protege rotas de API que alteram dados (cadastrar/editar/remover moto)."""
    @wraps(f)
    def decorada(*args, **kwargs):
        if not session.get('logado'):
            return jsonify({"ok": False, "erros": ["Sessão expirada. Faça login novamente."]}), 401
        return f(*args, **kwargs)
    return decorada


def codificar_foto(arquivo):
    """Lê um arquivo enviado e devolve uma data URI base64 (ou None)."""
    if not arquivo or arquivo.filename == "":
        return None

    if arquivo.mimetype not in ALLOWED_MIMETYPES:
        raise ValueError("Formato de imagem não suportado. Use PNG, JPG, JPEG, WEBP ou GIF.")

    conteudo = arquivo.read()
    base64_str = base64.b64encode(conteudo).decode("utf-8")
    return f"data:{arquivo.mimetype};base64,{base64_str}"


def codificar_fotos(arquivos):
    """Codifica uma lista de arquivos enviados, ignorando os vazios."""
    fotos = []
    for arquivo in arquivos:
        codificada = codificar_foto(arquivo)
        if codificada:
            fotos.append(codificada)
    return fotos


def moto_para_dict(moto):
    """moto = (id, marca, modelo, ano, cilindrada, quilometragem, categoria, fotos_json)"""
    fotos_json = moto[7]
    try:
        fotos = json.loads(fotos_json) if fotos_json else []
    except (TypeError, ValueError):
        fotos = []

    return {
        "id": moto[0],
        "marca": moto[1],
        "modelo": moto[2],
        "ano": moto[3],
        "cilindrada": moto[4],
        "quilometragem": moto[5],
        "categoria": moto[6],
        "fotos": fotos
    }


# ---------------- PÁGINAS ----------------

@app.route('/')
def pagina_loja():
    return render_template("loja.html")


@app.route('/login.html')
def pagina_login():
    if session.get('logado'):
        return redirect(url_for('admin_home'))
    return render_template("login.html")


@app.route('/admin')
@login_obrigatorio
def admin_home():
    return render_template("index.html")


@app.route('/moto.html')
@login_obrigatorio
def pagina_detalhe():
    return render_template("moto.html")


@app.route('/adicionar.html')
@login_obrigatorio
def pagina_adicionar():
    return render_template("adicionar.html")


@app.route('/editar.html')
@login_obrigatorio
def pagina_editar():
    return render_template("editar.html")


@app.route('/loja.html')
def pagina_loja_alias():
    return redirect(url_for('pagina_loja'))


# ---------------- LOGIN ----------------

@app.route("/api/login", methods=["POST"])
def api_login():
    usuario = request.form.get("usuario", "").strip()
    senha = request.form.get("senha", "").strip()

    if usuario == USUARIO_ADMIN and senha == SENHA_ADMIN:
        session['logado'] = True
        return jsonify({"ok": True, "mensagem": "Login feito com sucesso"})

    return jsonify({"ok": False, "erros": ["Usuário ou senha incorretos"]}), 401


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.pop('logado', None)
    return jsonify({"ok": True, "mensagem": "Sessão encerrada"})


# ---------------- API DE MOTOS ----------------

@app.route('/api/motos', methods=['POST'])
@login_obrigatorio_api
def api_motos():
    conexao = None
    cursor = None
    try:
        marca = request.form.get('marca')
        modelo = request.form.get('modelo')
        ano = request.form.get('ano')
        cilindrada = request.form.get('cilindrada')
        quilometragem = request.form.get('quilometragem')
        categoria = request.form.get('categoria')
        arquivos_fotos = request.files.getlist('fotos')

        if not all([marca, modelo, ano, cilindrada, quilometragem, categoria]):
            return jsonify({"ok": False, "erros": ["Preencha todos os campos"]}), 400

        try:
            fotos = codificar_fotos(arquivos_fotos)
        except ValueError as e:
            return jsonify({"ok": False, "erros": [str(e)]}), 400

        conexao = conectar_banco()
        cursor = conexao.cursor()

        cursor.execute("""
            INSERT INTO motos (marca, modelo, ano, cilindrada, quilometragem, categoria, fotos)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, marca, modelo, ano, cilindrada, quilometragem, categoria, fotos
        """, (marca, modelo, ano, cilindrada, quilometragem, categoria, json.dumps(fotos)))

        nova_moto = cursor.fetchone()
        conexao.commit()

        return jsonify({"ok": True, "mensagem": "Moto cadastrada com sucesso", "moto": moto_para_dict(nova_moto)})

    except psycopg2.errors.UniqueViolation:
        return jsonify({"ok": False, "erros": ["Moto já cadastrada"]}), 400

    except RequestEntityTooLarge:
        return jsonify({"ok": False, "erros": ["As fotos enviadas são muito grandes. Tente com menos fotos ou fotos menores."]}), 413

    except Exception as e:
        return jsonify({"ok": False, "erros": [f"Erro interno: {e}"]}), 500

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
        SELECT id, marca, modelo, ano, cilindrada, quilometragem, categoria, fotos
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
        SELECT id, marca, modelo, ano, cilindrada, quilometragem, categoria, fotos
        FROM motos
        WHERE id = %s
    """, (moto_id,))

    moto = cursor.fetchone()

    cursor.close()
    conexao.close()

    if not moto:
        return jsonify({"ok": False, "erros": ["Moto não encontrada"]}), 404

    return jsonify(moto_para_dict(moto))


@app.route("/api/motos/<int:moto_id>", methods=["PUT"])
@login_obrigatorio_api
def atualizar_moto(moto_id):
    conexao = None
    cursor = None
    try:
        marca = request.form.get('marca')
        modelo = request.form.get('modelo')
        ano = request.form.get('ano')
        cilindrada = request.form.get('cilindrada')
        quilometragem = request.form.get('quilometragem')
        categoria = request.form.get('categoria')

        fotos_existentes_raw = request.form.get('fotos_existentes', '[]')
        try:
            fotos_existentes = json.loads(fotos_existentes_raw)
            if not isinstance(fotos_existentes, list):
                fotos_existentes = []
        except (TypeError, ValueError):
            fotos_existentes = []

        arquivos_novas_fotos = request.files.getlist('fotos_novas')

        if not all([marca, modelo, ano, cilindrada, quilometragem, categoria]):
            return jsonify({"ok": False, "erros": ["Preencha todos os campos"]}), 400

        try:
            fotos_novas = codificar_fotos(arquivos_novas_fotos)
        except ValueError as e:
            return jsonify({"ok": False, "erros": [str(e)]}), 400

        fotos_final = fotos_existentes + fotos_novas

        conexao = conectar_banco()
        cursor = conexao.cursor()

        cursor.execute("""
            UPDATE motos
            SET marca = %s, modelo = %s, ano = %s, cilindrada = %s,
                quilometragem = %s, categoria = %s, fotos = %s
            WHERE id = %s
            RETURNING id, marca, modelo, ano, cilindrada, quilometragem, categoria, fotos
        """, (marca, modelo, ano, cilindrada, quilometragem, categoria, json.dumps(fotos_final), moto_id))

        moto_atualizada = cursor.fetchone()

        if not moto_atualizada:
            return jsonify({"ok": False, "erros": ["Moto não encontrada"]}), 404

        conexao.commit()

        return jsonify({"ok": True, "mensagem": "Moto atualizada com sucesso", "moto": moto_para_dict(moto_atualizada)})

    except RequestEntityTooLarge:
        return jsonify({"ok": False, "erros": ["As fotos enviadas são muito grandes. Tente com menos fotos ou fotos menores."]}), 413

    except Exception as e:
        return jsonify({"ok": False, "erros": [f"Erro interno: {e}"]}), 500

    finally:
        if cursor:
            cursor.close()
        if conexao:
            conexao.close()


@app.route("/api/motos/<int:moto_id>", methods=["DELETE"])
@login_obrigatorio_api
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


# ---------------- TRATAMENTO GLOBAL DE ERROS ----------------

@app.errorhandler(413)
def erro_arquivo_grande(e):
    return jsonify({"ok": False, "erros": ["As fotos enviadas são muito grandes. Tente com menos fotos ou fotos menores."]}), 413


@app.errorhandler(500)
def erro_interno(e):
    return jsonify({"ok": False, "erros": ["Erro interno no servidor. Tente novamente."]}), 500


if __name__ == '__main__':
    app.run(debug=True)
