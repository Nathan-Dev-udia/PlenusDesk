from flask import Flask, request, render_template, session, jsonify, redirect, url_for, flash
import xml.etree.ElementTree as ET
from datetime import datetime
import feedparser
import firebase_admin
from firebase_admin import credentials, auth
from firebase_admin import db
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from flask import Flask, redirect, request, session, url_for, render_template
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import os
import requests
import zipfile
import tempfile

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.secret_key = "chave_super_secreta"  # necessário para session
FIREBASE_URL = "https://plenus-acd5a-default-rtdb.firebaseio.com"

# Google Drive API
CLIENT_SECRETS_FILE = "client_secret_1041604443535-nqooelgk2qac7j4f9ufd0rlr7of4ltfj.apps.googleusercontent.com.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_ID = "1yuKTnPp6TbW9n1e8zUnSTK2I9afwpskG"  # pasta principal

@app.route("/authorize")
def authorize():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=url_for("oauth2callback", _external=True)
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    session["state"] = state
    return redirect(authorization_url)

@app.route("/oauth2callback")
def oauth2callback():
    state = session["state"]
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for("oauth2callback", _external=True)
    )
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    session["credentials"] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes
    }

    return redirect(url_for("cadastroguias"))

@app.route("/upload", methods=["POST"])
def upload_file():
    if "credentials" not in session:
        return redirect(url_for("authorize"))

    creds = Credentials(**session["credentials"])
    drive_service = build("drive", "v3", credentials=creds)

    # Pegando dados do formulário
    empresa_uid = request.form.get("empresa")
    titulo = request.form.get("titulo")
    files = request.files.getlist("file")

    if not empresa_uid or not titulo or not files:
        return "Empresa, título e arquivos são obrigatórios", 400

    # Pega folder_id da empresa
    ref_empresa = db.reference(f'/usuarios/{empresa_uid}')
    dados_empresa = ref_empresa.get()
    if not dados_empresa or not dados_empresa.get('folder_id'):
        flash("Empresa ou pasta não encontrada no Drive.", "danger")
        return redirect(url_for("cadastroguias"))

    pasta_empresa_id = dados_empresa['folder_id']

    # Cria subpasta com o título dentro da pasta da empresa
    folder_metadata = {
        "name": titulo,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [pasta_empresa_id]
    }
    folder = drive_service.files().create(body=folder_metadata, fields="id").execute()
    folder_id = folder.get("id")


    links = []

    for file in files:
        if file.filename == "":
            continue

        temp_path = os.path.join("/tmp", file.filename)
        file.save(temp_path)

        file_metadata = {"name": file.filename, "parents": [folder_id]}
        mimetype = "application/pdf" if file.filename.endswith(".pdf") else "application/zip"
        media = MediaFileUpload(temp_path, mimetype=mimetype)

        uploaded_file = drive_service.files().create(
            body=file_metadata, media_body=media, fields="id"
        ).execute()

        os.remove(temp_path)

        # Torna o arquivo público
        file_id = uploaded_file.get("id")
        drive_service.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"},
        ).execute()

        file_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
        links.append(file_link)

    response_html = f"Pasta criada: <b>{titulo}</b><br><br>"
    response_html += "<br>".join([f"<a href='{link}' target='_blank'>{link}</a>" for link in links])

    return response_html


########################################################################################################################
# inicializa só uma vez
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://plenus-acd5a-default-rtdb.firebaseio.com'
    })

# 🔹 Limite de upload (50 MB, pode ajustar se quiser)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

# Função para pegar notícias do RSS do Contábeis
def pegar_noticias():
    url = "https://www.contabeis.com.br/rss/noticias/"
    feed = feedparser.parse(url)

    noticias = []
    for entry in feed.entries[:6]:  # pega só as 6 primeiras
        # 🔹 Formata a data (quando existir)
        data_fmt = None
        if "published_parsed" in entry:
            try:
                dt = datetime.fromtimestamp(
                    __import__("time").mktime(entry.published_parsed)
                )
                data_fmt = dt.strftime("%d/%m/%Y - %H:%M")
            except Exception:
                data_fmt = entry.get("published", None)

        noticias.append({
            "titulo": entry.title,
            "link": entry.link,
            "imagem": entry.get("media_content", [{}])[0].get("url", None),  # às vezes tem imagem
            "data": data_fmt
        })
    return noticias


# Rota principal → abre o painel inicial (com a sidebar)
@app.route("/")
def principal():
    if "credentials" not in session:
        return redirect(url_for("authorize"))
    return render_template("home.html", noticias=pegar_noticias())

# Rota para a página de guias
@app.route("/guias")
def guias():
    try:
        # pega todos os usuários direto via SDK
        usuarios = db.reference("/usuarios").get() or {}
        todas_guias = []

        for uid, dados in usuarios.items():
            # evita crash se dados for None
            if not isinstance(dados, dict):
                continue

            nome_empresa = dados.get("nome", "Sem nome")
            cnpj = dados.get("cnpj", "CNPJ não informado")
            guias = dados.get("guias", {}) or {}

            for guia_id, guia in guias.items():
                if not isinstance(guia, dict):
                    continue
                todas_guias.append({
                    "titulo": guia.get("titulo", "Sem título"),
                    "instrucoes": guia.get("instrucoes", ""),
                    "data_postagem": guia.get("data_postagem", ""),  # formato: "YYYY-MM-DD HH:MM:SS"
                    "data_venc": guia.get("data_venc", ""),
                    "url": guia.get("url", "#"),
                    "empresa": nome_empresa,
                    "cnpj": cnpj
                })

        # Ordena por data_postagem (mais recente primeiro).
        # Se o campo estiver vazio, coloca como menor valor para ficar no final.
        def sort_key(g):
            dp = g.get("data_postagem") or ""
            return dp  # strings "YYYY-MM-DD HH:MM:SS" ordenam corretamente lexicograficamente

        todas_guias.sort(key=sort_key, reverse=True)

        return render_template("guias.html", guias=todas_guias)

    except Exception as e:
        # loga erro no console pra ajudar debug
        print("Erro ao carregar guias:", e)
        return "Erro ao carregar guias", 500


# 🔹 Lista usuários do Firebase e mostra em empresas.html
@app.route("/usuarios")
def listar_usuarios():
    ref = db.reference('/usuarios')
    data = ref.get()

    empresas = []
    if data:
        for uid, info in data.items():
            empresas.append({
                "uid": uid,
                "nome": info.get("nome", "Sem nome"),
                "cnpj": info.get("cnpj", ""),
                "email": info.get("email", ""),
                "ativo": info.get("ativo", False)
            })

    # Ordena alfabeticamente pelo nome (case-insensitive)
    empresas.sort(key=lambda x: (x.get("nome") or "").lower())

    return render_template("empresas.html", usuarios=empresas)


# Rota para cadastrar nova empresa
@app.route("/cadastrar_empresa", methods=["GET", "POST"])
def cadastrar_empresa():
    if "credentials" not in session:
        return redirect(url_for("authorize"))

    if request.method == "POST":
        nome = request.form["nome"]
        cnpj = request.form["cnpj"]
        email = request.form["email"]
        senha = request.form["senha"]

        try:
            # 1️⃣ Criar usuário no Firebase Authentication
            user = auth.create_user(
                email=email,
                password=senha,
                display_name=nome
            )

            # 2️⃣ Criar pasta da empresa no Google Drive
            creds = Credentials(**session["credentials"])
            drive_service = build("drive", "v3", credentials=creds)

            folder_metadata = {
                "name": nome,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [FOLDER_ID]  # pasta principal do projeto
            }

            folder = drive_service.files().create(body=folder_metadata, fields="id").execute()
            folder_id = folder.get("id")

            # 3️⃣ Salvar no Realtime Database
            ref = db.reference(f"usuarios/{user.uid}")
            ref.set({
                "nome": nome,
                "cnpj": cnpj,
                "email": email,
                "ativo": True,
                "folder_id": folder_id
            })

            flash("Empresa cadastrada com sucesso!", "success")
            return redirect(url_for("listar_usuarios"))

        except Exception as e:
            flash(f"Erro ao cadastrar empresa: {e}", "danger")

    return render_template("cadastrar_empresa.html")


# Rota para editar empresa
@app.route("/editar_empresa/<uid>", methods=["GET", "POST"])
def editar_empresa(uid):
    ref = db.reference(f'/usuarios/{uid}')
    dados = ref.get()

    if request.method == "POST":
        novo_nome = request.form.get("nome")
        novo_cnpj = request.form.get("cnpj")
        novo_email = request.form.get("email")

        # Atualiza no RTDB
        ref.update({
            "nome": novo_nome,
            "cnpj": novo_cnpj,
            "email": novo_email
        })

        # Atualiza também no Auth
        auth.update_user(
            uid,
            email=novo_email,
            display_name=novo_nome
        )

        return redirect(url_for("listar_usuarios"))

    return render_template("editar_empresa.html", uid=uid, dados=dados)


# 🔹 Versão JSON opcional (pode ser consumida no front)
@app.route("/api/usuarios")
def api_usuarios():
    usuarios = []
    for user in auth.list_users().iterate_all():
        usuarios.append({
            "uid": user.uid,
            "email": user.email,
            "nome": user.display_name
        })
    return jsonify(usuarios)


@app.route("/guiaspostadas")
def guiaspostadas():
    return render_template("guiaspostadas.html", guias=session.get("guias", []))

# é pra listar as empresas no select do cadastro de guias
@app.route("/empresas")
def api_empresas():
    try:
        ref = db.reference('/usuarios')
        data = ref.get()
        empresas = []
        if data:
            for uid, info in data.items():
                empresas.append({
                    "id": uid,  # usado como value no select
                    "nome": info.get("nome", "Sem nome")
                })

        empresas.sort(key=lambda x: (x.get("nome") or "").lower())
        return jsonify(empresas)
    except Exception as e:
        return jsonify([]), 500



# Rota para cadastrar guias vinculando a empresa
@app.route('/cadastroguias')
def cadastroguias():
    # Pega todas as empresas do Firebase
    ref = db.reference('/usuarios')
    data = ref.get()

    empresas = []
    if data:
        for uid, info in data.items():
            empresas.append({
                "uid": uid,
                "nome": info.get("nome", "Sem nome")
            })

    empresas.sort(key=lambda x: (x.get("nome") or "").lower())
    return render_template('cadastroguias.html', empresas=empresas)


# Rota para processar o formulário de cadastro de guias
@app.route("/post_guia", methods=["POST"])
def post_guia():
    if "credentials" not in session:
        return redirect(url_for("authorize"))

    creds = Credentials(**session["credentials"])
    drive_service = build("drive", "v3", credentials=creds)

    # 🔹 Dados do formulário
    empresa_uid = request.form.get("empresa")
    titulo = request.form.get("titulo")
    descricao = request.form.get("descricao")
    data_vencimento = request.form.get("data_vencimento")
    anexos = request.files.getlist("file")  # agora pega lista de arquivos

    if not empresa_uid or not titulo or not anexos:
        flash("Empresa, título e arquivos são obrigatórios.", "danger")
        return redirect(url_for("cadastroguias"))

    # 🔹 Busca a empresa no Firebase
    ref_empresa = db.reference(f"/usuarios/{empresa_uid}")
    dados_empresa = ref_empresa.get()
    if not dados_empresa or not dados_empresa.get("folder_id"):
        flash("Empresa ou pasta não encontrada no Drive.", "danger")
        return redirect(url_for("cadastroguias"))

    pasta_empresa_id = dados_empresa["folder_id"]

    # 🔹 Cria subpasta no Drive
    folder_metadata = {
        "name": titulo,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [pasta_empresa_id],
    }
    pasta = drive_service.files().create(body=folder_metadata, fields="id").execute()
    pasta_id = pasta.get("id")

    # 🔹 Torna a pasta pública
    drive_service.permissions().create(
        fileId=pasta_id,
        body={"role": "reader", "type": "anyone"},
    ).execute()

    # 🔹 Upload dos arquivos
    for file in anexos:
        if file.filename == "":
            continue

        temp_path = os.path.join("/tmp", file.filename)
        file.save(temp_path)

        file_metadata = {"name": file.filename, "parents": [pasta_id]}
        mimetype = "application/pdf" if file.filename.endswith(".pdf") else "application/zip"
        media = MediaFileUpload(temp_path, mimetype=mimetype)

        uploaded_file = drive_service.files().create(
            body=file_metadata, media_body=media, fields="id"
        ).execute()
        os.remove(temp_path)

        # Torna público
        drive_service.permissions().create(
            fileId=uploaded_file.get("id"),
            body={"role": "reader", "type": "anyone"},
        ).execute()

    # 🔹 Link da pasta
    pasta_link = f"https://drive.google.com/drive/folders/{pasta_id}?usp=sharing"

    # 🔹 Cria registro local
    nova_guia = {
        "id": 1,
        "titulo": titulo,
        "descricao": descricao,
        "data_postagem": datetime.now().strftime("%d/%m/%Y"),
        "hora_postagem": datetime.now().strftime("%H:%M"),
        "nome_empresa": dados_empresa.get("nome", "Empresa Desconhecida"),
        "cnpj": dados_empresa.get("cnpj", "00.000.000/0001-00"),
        "anexo_url": pasta_link,
        "status": {"concluido": False},
    }

    if "guias" not in session:
        session["guias"] = []
    session["guias"].append(nova_guia)

    # 🔹 Salva no Firebase
    guia_data = {
        "titulo": titulo,
        "instrucoes": descricao,
        "url": pasta_link,
        "data_postagem": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "concluida": False,
    }
    if data_vencimento:
        guia_data["data_venc"] = data_vencimento

    guias_ref = db.reference(f"/usuarios/{empresa_uid}/guias")
    guias_ref.push(guia_data)

    flash("Guia enviada e registrada no Firebase com sucesso!", "success")
    return redirect(url_for("guias"))


# Rota do comparador de cupons
@app.route("/cupons", methods=["GET", "POST"])
def cupons():
    results = []
    sequence_breaks = []

    if request.method == "POST":
        files = request.files.getlist("xmlfiles")
        temp_results = []

        for f in files:
            try:
                tree = ET.parse(f)
                root = tree.getroot()

                infNFe = root.find(".//{http://www.portalfiscal.inf.br/nfe}infNFe")
                if infNFe is None:
                    continue

                nNF = infNFe.find(".//{http://www.portalfiscal.inf.br/nfe}ide/{http://www.portalfiscal.inf.br/nfe}nNF")
                nNF_text = nNF.text if nNF is not None else "N/A"
                id_infNFe = infNFe.attrib.get("Id", "N/A")

                temp_results.append({
                    "nNF": nNF_text,
                    "id_infNFe": id_infNFe,
                })

            except Exception:
                continue

        # Checa duplicados
        nNF_count = {}
        id_count = {}

        for r in temp_results:
            nNF_count[r["nNF"]] = nNF_count.get(r["nNF"], 0) + 1
            id_count[r["id_infNFe"]] = id_count.get(r["id_infNFe"], 0) + 1

        for r in temp_results:
            r["duplicate"] = nNF_count[r["nNF"]] > 1 or id_count[r["id_infNFe"]] > 1

        # Quebra de sequência
        broken_sequence_indices = set()
        try:
            numeros_com_indices = [(i, int(r["nNF"])) for i, r in enumerate(temp_results) if r["nNF"].isdigit()]
            numeros_ordenados = sorted(numeros_com_indices, key=lambda x: x[1])

            for idx in range(len(numeros_ordenados) - 1):
                atual_idx, atual_num = numeros_ordenados[idx]
                proximo_idx, proximo_num = numeros_ordenados[idx + 1]
                if proximo_num != atual_num + 1:
                    broken_sequence_indices.add(proximo_idx)
                    sequence_breaks.append((atual_num, proximo_num))

        except Exception:
            pass

        for i, r in enumerate(temp_results):
            r["sequence_error"] = i in broken_sequence_indices

        results = temp_results

    return render_template("cupons.html", results=results, sequence_breaks=sequence_breaks)


# Rota para a página de valores / financeiro
@app.route("/valores", methods=["GET", "POST"])
def consultfinan():
    # 🔹 sempre começa zerado quando abre a página
    if request.method == "GET":
        session["pagamentos"] = []

    action = request.form.get("action")
    filtro_mes = request.form.get("filtro_mes")
    periodo_inicio = request.form.get("periodo_inicio")
    periodo_fim = request.form.get("periodo_fim")
    total_valor = 0.0

    pagamentos = session.get("pagamentos", [])

    if request.method == "POST":
        files = request.files.getlist("xmlfiles")

        if action == "import" and files:
            # Importa XMLs, mas evita notas repetidas pela chave <chNFe>
            chaves_existentes = {p["chave"] for p in pagamentos}
            for f in files:
                try:
                    tree = ET.parse(f)
                    root = tree.getroot()

                    infNFe = root.find(".//{http://www.portalfiscal.inf.br/nfe}infNFe")
                    if infNFe is None:
                        continue

                    # pega chave única da nota
                    chNFe_tag = root.find(".//{http://www.portalfiscal.inf.br/nfe}chNFe")
                    if chNFe_tag is None:
                        continue
                    chave = chNFe_tag.text.strip()

                    if chave in chaves_existentes:
                        continue  # pula notas duplicadas
                    chaves_existentes.add(chave)

                    # número da fatura (quando existir)
                    fat = infNFe.find(".//{http://www.portalfiscal.inf.br/nfe}cobr/{http://www.portalfiscal.inf.br/nfe}fat")
                    nFat = fat.find("{http://www.portalfiscal.inf.br/nfe}nFat").text if fat is not None and fat.find("{http://www.portalfiscal.inf.br/nfe}nFat") is not None else "N/A"

                    cobr = infNFe.find(".//{http://www.portalfiscal.inf.br/nfe}cobr")
                    if cobr is not None:
                        dup_list = cobr.findall(".//{http://www.portalfiscal.inf.br/nfe}dup")
                        for dup in dup_list:
                            dVenc = dup.find("{http://www.portalfiscal.inf.br/nfe}dVenc")
                            vDup = dup.find("{http://www.portalfiscal.inf.br/nfe}vDup")
                            if dVenc is None or vDup is None:
                                continue
                            # formata data de vencimento
                            try:
                                venc_fmt = datetime.strptime(dVenc.text, "%Y-%m-%d").strftime("%d/%m/%Y")
                            except:
                                venc_fmt = dVenc.text
                            pagamento = {
                                "chave": chave,
                                "nota": nFat,
                                "vencimento": venc_fmt,
                                "valor": vDup.text
                            }
                            pagamentos.append(pagamento)

                except Exception as e:
                    print("Erro ao ler XML:", e)
                    continue
            session["pagamentos"] = pagamentos  # salva na sessão

        elif action == "filter":
            # Apenas filtra os pagamentos já importados
            filtrados = []
            for p in pagamentos:
                try:
                    dt_venc = datetime.strptime(p["vencimento"], "%d/%m/%Y")
                except:
                    continue

                # Filtro período
                dt_inicio = datetime.strptime(periodo_inicio, "%Y-%m-%d") if periodo_inicio else datetime.min
                dt_fim = datetime.strptime(periodo_fim, "%Y-%m-%d") if periodo_fim else datetime.max
                # Filtro mês
                if periodo_inicio or periodo_fim:
                    if dt_inicio <= dt_venc <= dt_fim:
                        filtrados.append(p)
                elif filtro_mes:
                    dt_mes = datetime.strptime(filtro_mes, "%Y-%m")
                    if dt_venc.year == dt_mes.year and dt_venc.month == dt_mes.month:
                        filtrados.append(p)
                else:
                    filtrados.append(p)
            pagamentos = filtrados

        elif action == "clear":
            # 🔹 botão para limpar manualmente
            pagamentos = []
            session["pagamentos"] = []

    # Calcula total
    for p in pagamentos:
        try:
            total_valor += float(p["valor"].replace(',', '.'))
        except:
            continue

    return render_template("valores.html",
                           pagamentos=pagamentos,
                           filtro_mes=filtro_mes,
                           periodo_inicio=periodo_inicio,
                           periodo_fim=periodo_fim,
                           total_valor=total_valor)


if __name__ == "__main__":
    app.run(debug=True)