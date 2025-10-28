from flask import Flask, render_template, request, session
import xml.etree.ElementTree as ET
from datetime import datetime

app = Flask(__name__)
app.secret_key = "chave-super-secreta"  # necessária para usar session
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # limite de upload: 50MB


# ----------------------------------------------
# 🔹 Página inicial
# ----------------------------------------------
@app.route("/")
def home():
    return render_template("home.html")


# ----------------------------------------------
# 🔹 Comparador de Cupons Fiscais
# ----------------------------------------------
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

                # número da nota fiscal
                nNF = infNFe.find(".//{http://www.portalfiscal.inf.br/nfe}ide/{http://www.portalfiscal.inf.br/nfe}nNF")
                nNF_text = nNF.text if nNF is not None else "N/A"

                # id da NFe
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

        # Checa quebras de sequência numérica
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


# ----------------------------------------------
# 🔹 Página de valores / financeiro
# ----------------------------------------------
@app.route("/valores", methods=["GET", "POST"])
def valores():
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
            # Importa XMLs evitando duplicados
            chaves_existentes = {p["chave"] for p in pagamentos}
            for f in files:
                try:
                    tree = ET.parse(f)
                    root = tree.getroot()

                    infNFe = root.find(".//{http://www.portalfiscal.inf.br/nfe}infNFe")
                    if infNFe is None:
                        continue

                    # chave única
                    chNFe_tag = root.find(".//{http://www.portalfiscal.inf.br/nfe}chNFe")
                    if chNFe_tag is None:
                        continue
                    chave = chNFe_tag.text.strip()

                    if chave in chaves_existentes:
                        continue
                    chaves_existentes.add(chave)

                    # número da fatura
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
                            try:
                                venc_fmt = datetime.strptime(dVenc.text, "%Y-%m-%d").strftime("%d/%m/%Y")
                            except:
                                venc_fmt = dVenc.text
                            pagamentos.append({
                                "chave": chave,
                                "nota": nFat,
                                "vencimento": venc_fmt,
                                "valor": vDup.text
                            })

                except Exception as e:
                    print("Erro ao ler XML:", e)
                    continue
            session["pagamentos"] = pagamentos

        elif action == "filter":
            filtrados = []
            for p in pagamentos:
                try:
                    dt_venc = datetime.strptime(p["vencimento"], "%d/%m/%Y")
                except:
                    continue

                dt_inicio = datetime.strptime(periodo_inicio, "%Y-%m-%d") if periodo_inicio else datetime.min
                dt_fim = datetime.strptime(periodo_fim, "%Y-%m-%d") if periodo_fim else datetime.max

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
