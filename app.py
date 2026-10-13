import os
import math
import io
from datetime import datetime
import re
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import pandas as pd
from supabase import create_client

app = Flask(__name__)
app.secret_key = "sua_chave_secreta_super_segura"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://emjrmvdmgkzrhknjzlky.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVtanJtdmRtZ2t6cmhrbmp6bGt5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTExNzEzMjQsImV4cCI6MjEwNjc0NzMyNH0.k3qGltlfTc1Kw1eyuj0n1IrzfQgY9y5uajh6UX-RTy8")

def init_supabase():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Erro ao conectar ao Supabase: {e}")
        return None

def carregar_dados():
    supabase = init_supabase()
    colunas_padrao = ["id", "data", "tipo", "carga", "codigo", "perfis", "sobras", "status", "policorte", "agrupado"]
    
    if not supabase:
        return pd.DataFrame(columns=["ID", "Data", "Tipo", "Carga", "Codigo", "Perfis", "Sobras", "Status", "Policorte", "Agrupado"])
    
    try:
        response = supabase.table("Sistema-Corte").select("*").execute()
        if not response.data:
            return pd.DataFrame(columns=["ID", "Data", "Tipo", "Carga", "Codigo", "Perfis", "Sobras", "Status", "Policorte", "Agrupado"])
        
        df = pd.DataFrame(response.data)
        df.columns = [str(c).lower().strip() for c in df.columns]
        
        for col in colunas_padrao:
            if col not in df.columns:
                df[col] = ""
                
        mapa_colunas = {
            "id": "ID", "data": "Data", "tipo": "Tipo", "carga": "Carga", 
            "codigo": "Codigo", "perfis": "Perfis", "sobras": "Sobras", 
            "status": "Status", "policorte": "Policorte", "agrupado": "Agrupado"
        }
        df = df.rename(columns=mapa_colunas)
        return df
    except Exception as e:
        print(f"Erro ao carregar dados do Supabase: {e}")
        return pd.DataFrame(columns=["ID", "Data", "Tipo", "Carga", "Codigo", "Perfis", "Sobras", "Status", "Policorte", "Agrupado"])

def salvar_dados(df):
    supabase = init_supabase()
    if not supabase or df.empty:
        return
        
    try:
        res = supabase.table("Sistema-Corte").select("id").execute()
        ids_existentes = [r["id"] for r in res.data if r.get("id") is not None]
        proximo_id = max(ids_existentes) + 1 if ids_existentes else 1

        df_envio = df.copy()
        df_envio = df_envio.fillna("")
        
        records = []
        for _, row in df_envio.iterrows():
            rec = row.to_dict()
            
            registro_limpo = {
                "Data": str(rec.get("Data", rec.get("data", ""))),
                "Tipo": str(rec.get("Tipo", rec.get("tipo", "Ordens Criadas"))),
                "Carga": str(rec.get("Carga", rec.get("carga", ""))),
                "Codigo": str(rec.get("Codigo", rec.get("codigo", ""))),
                "Perfis": str(rec.get("Perfis", rec.get("perfis", ""))),
                "Sobras": str(rec.get("Sobras", rec.get("sobras", ""))),
                "Status": str(rec.get("Status", rec.get("status", "Pendente"))),
                "Policorte": str(rec.get("Policorte", rec.get("policorte", "Nenhuma"))),
                "Agrupado": str(rec.get("Agrupado", rec.get("agrupado", "Não")))
            }
            
            id_val = rec.get("ID", rec.get("id"))
            if id_val is not None and str(id_val).strip() != "" and str(id_val).lower() != "nan":
                try:
                    registro_limpo["id"] = int(float(str(id_val)))
                except ValueError:
                    registro_limpo["id"] = proximo_id
                    proximo_id += 1
            else:
                registro_limpo["id"] = proximo_id
                proximo_id += 1

            records.append(registro_limpo)

        if records:
            supabase.table("Sistema-Corte").upsert(records).execute()
    except Exception as e:
        print(f"ERRO CRÍTICO AO SALVAR NO SUPABASE: {e}")

def eh_perfil(nome):
    nome_upper = str(nome).strip().upper()
    baguetes = ["BB01B", "BJ05", "BJ03", "BJ06L"]
    return nome_upper.startswith("ES") or nome_upper in baguetes

def paginar_dataframe(df, pagina_atual, por_pagina=20):
    total_itens = len(df)
    total_paginas = math.ceil(total_itens / por_pagina) if total_itens > 0 else 1
    pagina_atual = max(1, min(pagina_atual, total_paginas))
    
    inicio = (pagina_atual - 1) * por_pagina
    fim = inicio + por_pagina
    
    df_fatia = df.iloc[inicio:fim]
    return df_fatia.to_dict(orient="records"), pagina_atual, total_paginas, total_itens

def aplicar_filtros(df, request_args):
    if df.empty:
        return df
    
    f_codigo = request_args.get('f_codigo', '').strip().lower()
    f_carga = request_args.get('f_carga', '').strip().lower()
    f_perfil = request_args.get('f_perfil', '').strip().lower()
    f_sobra = request_args.get('f_sobra', '').strip().lower()
    f_data = request_args.get('f_data', '').strip()

    df_filtrado = df.copy()

    if f_codigo:
        df_filtrado = df_filtrado[df_filtrado["Codigo"].astype(str).str.lower().str.contains(f_codigo, na=False)]
    if f_carga:
        df_filtrado = df_filtrado[df_filtrado["Carga"].astype(str).str.lower().str.contains(f_carga, na=False)]
    if f_perfil:
        df_filtrado = df_filtrado[df_filtrado["Perfis"].astype(str).str.lower().str.contains(f_perfil, na=False)]
    if f_sobra:
        df_filtrado = df_filtrado[df_filtrado["Sobras"].astype(str).str.lower().str.contains(f_sobra, na=False)]
    if f_data:
        def converte_data_para_busca(data_str):
            try:
                partes = data_str.split()[0].split('/')
                if len(partes) == 3:
                    return f"{partes[2]}-{partes[1]}-{partes[0]}"
            except:
                pass
            return ""
        df_filtrado["DataFiltro"] = df_filtrado["Data"].apply(converte_data_para_busca)
        df_filtrado = df_filtrado[df_filtrado["DataFiltro"] == f_data]
        df_filtrado = df_filtrado.drop(columns=["DataFiltro"])

    return df_filtrado

def extrair_parametros_filtros(req_args):
    return {
        'f_codigo': req_args.get('f_codigo', ''),
        'f_carga': req_args.get('f_carga', ''),
        'f_perfil': req_args.get('f_perfil', ''),
        'f_sobra': req_args.get('f_sobra', ''),
        'f_data': req_args.get('f_data', ''),
        'ordem_id': req_args.get('ordem_id', 'padrao'),
        'juntar_codigos': req_args.get('juntar_codigos', ''),
        'page': req_args.get('page', '1')
    }

@app.route('/enviar_lote', methods=['POST'])
def enviar_lote():
    ids_selecionados = request.form.getlist('ids_lote')
    destino = request.form.get('destino_lote', 'Policorte 1')
    aba_origem = request.form.get('aba_origem', 'separacao')
    filtros_params = extrair_parametros_filtros(request.args)
    
    if ids_selecionados:
        df_atual = carregar_dados()
        ids_ints = [int(i) for i in ids_selecionados if str(i).isdigit()]
        mask = pd.to_numeric(df_atual["ID"], errors="coerce").isin(ids_ints)
        df_atual.loc[mask, "Status"] = "Em Corte"
        df_atual.loc[mask, "Policorte"] = destino
        salvar_dados(df_atual)
        flash(f"{len(ids_selecionados)} ordem(ns) enviada(s) para a {destino}!", "success")
    else:
        flash("Nenhuma ordem selecionada!", "warning")
        
    return redirect(url_for('index', aba=aba_origem, **filtros_params))

@app.route('/priorizar_lote', methods=['POST'])
def priorizar_lote():
    ids_selecionados = request.form.getlist('ids_lote')
    filtros_params = extrair_parametros_filtros(request.args)
    if ids_selecionados:
        df_atual = carregar_dados()
        ids_ints = [int(i) for i in ids_selecionados if str(i).isdigit()]
        mask = pd.to_numeric(df_atual["ID"], errors="coerce").isin(ids_ints)
        df_atual.loc[mask, "Tipo"] = "Ordens Criadas"
        salvar_dados(df_atual)
        flash(f"{len(ids_selecionados)} ordem(ns) marcada(s) como Prioridade!", "success")
    else:
        flash("Nenhuma ordem selecionada!", "warning")
    return redirect(url_for('index', aba='ordens', **filtros_params))

@app.route('/excluir_lote', methods=['POST'])
def excluir_lote():
    ids_selecionados = request.form.getlist('ids_lote')
    filtros_params = extrair_parametros_filtros(request.args)
    if ids_selecionados:
        supabase = init_supabase()
        ids_ints = [int(i) for i in ids_selecionados if str(i).isdigit()]
        try:
            for cid in ids_ints:
                supabase.table("Sistema-Corte").delete().eq("id", cid).execute()
            flash(f"{len(ids_selecionados)} ordem(ns) excluída(s) com sucesso!", "danger")
        except Exception as e:
            flash(f"Erro ao excluir: {e}", "danger")
    else:
        flash("Nenhuma ordem selecionada!", "warning")
    return redirect(url_for('index', aba='ordens', **filtros_params))

@app.route('/agrupar_lote', methods=['POST'])
def agrupar_lote():
    ids_selecionados = request.form.getlist('ids_lote')
    filtros_params = extrair_parametros_filtros(request.args)
    if len(ids_selecionados) < 2:
        flash("Selecione pelo menos duas ordens para agrupar!", "warning")
        return redirect(url_for('index', aba='separacao', **filtros_params))
    
    df_atual = carregar_dados()
    ids_ints = [int(i) for i in ids_selecionados if str(i).isdigit()]
    
    mask_sel = pd.to_numeric(df_atual["ID"], errors="coerce").isin(ids_ints)
    df_sel = df_atual[mask_sel]
    
    if df_sel.empty:
        flash("Nenhuma ordem válida encontrada para agrupamento.", "danger")
        return redirect(url_for('index', aba='separacao', **filtros_params))
    
    codigosUnicos = df_sel["Codigo"].astype(str).str.strip().unique()
    if len(codigosUnicos) > 1:
        flash("Erro: Você só pode agrupar ordens que possuem exatamente o mesmo Código!", "danger")
        return redirect(url_for('index', aba='separacao', **filtros_params))
    
    codigo_comum = codigosUnicos[0]
    
    def somar_itens_str(series_str):
        soma_dict = {}
        for texto in series_str:
            if not texto or str(texto).strip().lower() in ["nenhum", "nenhuma", ""]:
                continue
            matches = re.findall(r'(.+?)\s*\(Qtd:\s*([\d\.,]+)\)', str(texto))
            for item_nome, qtd_str in matches:
                item_nome = item_nome.strip()
                try:
                    qtd_val = float(qtd_str.replace(',', '.'))
                except ValueError:
                    qtd_val = 0.0
                soma_dict[item_nome] = soma_dict.get(item_nome, 0.0) + qtd_val
                
        if not soma_dict:
            return "Nenhum"
        
        resultado_partes = []
        for item, val in soma_dict.items():
            if val.is_integer():
                val_str = f"{int(val):,}".replace(',', '.')
            else:
                val_str = f"{val:.2f}".replace('.', ',')
            resultado_partes.append(f"{item} (Qtd: {val_str})")
        return " | ".join(resultado_partes)

    perfis_somados = somar_itens_str(df_sel["Perfis"])
    sobras_somadas = somar_itens_str(df_sel["Sobras"])
    
    primeiro_id = int(df_sel.iloc[0]["ID"])
    
    mask_primeiro = pd.to_numeric(df_atual["ID"], errors="coerce") == primeiro_id
    df_atual.loc[mask_primeiro, "Perfis"] = perfis_somados
    df_atual.loc[mask_primeiro, "Sobras"] = sobras_somadas
    df_atual.loc[mask_primeiro, "Agrupado"] = "Sim"
    
    ids_para_remover = [i for i in ids_ints if i != primeiro_id]
    supabase = init_supabase()
    try:
        for cid in ids_para_remover:
            supabase.table("Sistema-Corte").delete().eq("id", cid).execute()
    except Exception as e:
        print(f"Erro ao remover ordens duplicadas do agrupamento: {e}")
        
    df_atual = df_atual[~pd.to_numeric(df_atual["ID"], errors="coerce").isin(ids_para_remover)]
    salvar_dados(df_atual)
    
    flash(f"Ordens do código {codigo_comum} agrupadas com sucesso (Quantidades somadas)!", "success")
    return redirect(url_for('index', aba='separacao', **filtros_params))

@app.route('/editar_quantidade/<int:id_ordem>', methods=['POST'])
def editar_quantidade(id_ordem):
    nova_qtd = request.form.get('nova_quantidade', '').strip()
    aba_origem = request.args.get('aba', 'separacao')
    filtros_params = extrair_parametros_filtros(request.args)
    
    try:
        nova_qtd_val = float(nova_qtd.replace(',', '.'))
        if nova_qtd_val <= 0:
            flash("A quantidade deve ser maior que zero!", "warning")
            return redirect(url_for('index', aba=aba_origem, **filtros_params))
    except ValueError:
        flash("Quantidade inválida informada!", "danger")
        return redirect(url_for('index', aba=aba_origem, **filtros_params))

    df_atual = carregar_dados()
    mask = pd.to_numeric(df_atual["ID"], errors="coerce") == id_ordem
    ordem_original = df_atual[mask]

    if ordem_original.empty:
        flash("Ordem não encontrada!", "danger")
        return redirect(url_for('index', aba=aba_origem, **filtros_params))

    rec = ordem_original.iloc[0].to_dict()
    
    def recalcular_string(texto, fator_mult):
        if not texto or str(texto).strip().lower() in ["nenhum", "nenhuma", ""]:
            return texto
        
        matches = re.findall(r'(.+?)\s*\(Qtd:\s*([\d\.,]+)\)', str(texto))
        if not matches:
            return texto

        partes = []
        for item_nome, q_str in matches:
            try:
                q_val = float(q_str.replace(',', '.'))
                q_nova = q_val * fator_mult
                if q_nova.is_integer():
                    q_nova_str = f"{int(q_nova):,}".replace(',', '.')
                else:
                    q_nova_str = f"{q_nova:.2f}".replace('.', ',')
                partes.append(f"{item_nome.strip()} (Qtd: {q_nova_str})")
            except ValueError:
                partes.append(f"{item_nome.strip()} (Qtd: {q_str})")
        return " | ".join(partes)

    matches_p = re.findall(r'\(Qtd:\s*([\d\.,]+)\)', str(rec.get("Perfis", "")))
    qtd_atual_orig = float(matches_p[0].replace(',', '.')) if matches_p else nova_qtd_val

    if nova_qtd_val >= qtd_atual_orig:
        flash("A nova quantidade precisa ser menor que a quantidade atual para haver divisão!", "warning")
        return redirect(url_for('index', aba=aba_origem, **filtros_params))

    fator_original = nova_qtd_val / qtd_atual_orig
    fator_resto = (qtd_atual_orig - nova_qtd_val) / qtd_atual_orig

    df_atual.loc[mask, "Perfis"] = recalcular_string(rec.get("Perfis", ""), fator_original)
    df_atual.loc[mask, "Sobras"] = recalcular_string(rec.get("Sobras", ""), fator_original)

    nova_ordem = {
        "ID": "",
        "Data": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "Tipo": rec.get("Tipo", "Ordens Criadas"),
        "Carga": rec.get("Carga", ""),
        "Codigo": rec.get("Codigo", ""),
        "Perfis": recalcular_string(rec.get("Perfis", ""), fator_resto),
        "Sobras": recalcular_string(rec.get("Sobras", ""), fator_resto),
        "Status": rec.get("Status", "Pendente"),
        "Policorte": rec.get("Policorte", "Nenhuma"),
        "Agrupado": "Não"
    }

    df_nova = pd.DataFrame([nova_ordem])
    df_atual = pd.concat([df_atual, df_nova], ignore_index=True)

    salvar_dados(df_atual)
    flash(f"Ordem {rec.get('Codigo')} editada para {nova_qtd_val} e gerada nova ordem com o restante!", "success")

    return redirect(url_for('index', aba=aba_origem, **filtros_params))

@app.route('/baixar_excel')
def baixar_excel():
    df_global = carregar_dados()
    if df_global.empty:
        flash("Não há dados para exportar.", "warning")
        return redirect(url_for('index', aba='finalizadas'))
    
    status_clean = df_global["Status"].astype(str).str.strip()
    df_fin = df_global[status_clean == "Finalizado"]
    df_fin = aplicar_filtros(df_fin, request.args)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_fin.to_excel(writer, index=False, sheet_name='Finalizadas')
    output.seek(0)
    
    nome_arquivo = f"Relatorio_Finalizadas_{datetime.now().strftime('%d-%m-%Y_%H%M')}.xlsx"
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=nome_arquivo)

@app.route('/mudar_status/<int:id_ordem>/<novo_status>/<policorte>', methods=['POST'])
def mudar_status(id_ordem, novo_status, policorte):
    aba_origem = request.args.get('aba', 'ordens')
    filtros_params = extrair_parametros_filtros(request.args)
    
    df_atual = carregar_dados()
    mask = pd.to_numeric(df_atual["ID"], errors="coerce") == id_ordem
    
    if novo_status == "Pendente":
        df_atual.loc[mask, "Status"] = "Pendente"
        df_atual.loc[mask, "Policorte"] = "Nenhuma"
        flash(f"ID {id_ordem} voltou para Separação!", "info")
    elif novo_status == "Finalizado":
        df_atual.loc[mask, "Status"] = "Finalizado"
        df_atual.loc[mask, "Policorte"] = policorte if policorte != "Nenhuma" else "Finalizado"
        flash(f"ID {id_ordem} finalizado com sucesso!", "success")
        
    salvar_dados(df_atual)
    return redirect(url_for('index', aba=aba_origem, **filtros_params))

@app.route('/', methods=['GET', 'POST'])
def index():
    df_global = carregar_dados()
    aba_ativa = request.args.get('aba', request.form.get('aba_origem', 'ordens'))
    
    if request.method == 'POST' and request.form.get('acao') == 'cadastrar_ordem':
        txt_ordens = request.form.get('txt_ordens', '')
        txt_cargas = request.form.get('txt_cargas', '')
        tipo_selecionado = request.form.get('tipo_selecionado', 'Ordens Criadas')
        
        if txt_ordens.strip():
            linhas = txt_ordens.strip().split("\n")
            dados_brutos = []
            codigo_atual = ""
            carga_informada = "" if tipo_selecionado == "Ordens Criadas" else str(txt_cargas).strip()

            for linha in linhas:
                partes = linha.strip().split()
                if not partes:
                    continue
                
                if len(partes) == 1:
                    codigo_atual = partes[0]
                elif len(partes) >= 3:
                    codigo_atual = partes[0]
                    item_secundario = partes[1]
                    qtd = partes[2]
                    tipo_item = "Perfil" if eh_perfil(item_secundario) else "Sobra"
                    
                    dados_brutos.append({
                        "Codigo": codigo_atual, 
                        "Item": item_secundario, 
                        "Qtd": qtd, 
                        "TipoItem": tipo_item
                    })
                elif len(partes) == 2 and (eh_perfil(partes[0]) or not partes[1].isdigit()):
                    if codigo_atual:
                        item_secundario = partes[0]
                        qtd = partes[1]
                        tipo_item = "Perfil" if eh_perfil(item_secundario) else "Sobra"
                        dados_brutos.append({
                            "Codigo": codigo_atual, 
                            "Item": item_secundario, 
                            "Qtd": qtd, 
                            "TipoItem": tipo_item
                        })
            
            if dados_brutos:
                df_temp = pd.DataFrame(dados_brutos)
                data_atual = datetime.now().strftime("%d/%m/%Y %H:%M")

                novas_linhas = []
                for codigo, grupo in df_temp.groupby("Codigo", sort=False):
                    perfis_lista = [f"{r['Item']} (Qtd: {r['Qtd']})" for _, r in grupo.iterrows() if r['TipoItem'] == "Perfil"]
                    sobras_lista = [f"{r['Item']} (Qtd: {r['Qtd']})" for _, r in grupo.iterrows() if r['TipoItem'] == "Sobra"]

                    novas_linhas.append({
                        "ID": "",
                        "Data": data_atual,
                        "Carga": carga_informada,
                        "Codigo": str(codigo).strip(),
                        "Perfis": " | ".join(perfis_lista) if perfis_lista else "Nenhum",
                        "Sobras": " | ".join(sobras_lista) if sobras_lista else "Nenhuma",
                        "Tipo": str(tipo_selecionado),
                        "Status": "Pendente",
                        "Policorte": "Nenhuma",
                        "Agrupado": "Não"
                    })

                if novas_linhas:
                    df_novas = pd.DataFrame(novas_linhas)
                    if df_global.empty:
                        df_global = df_novas
                    else:
                        df_global = pd.concat([df_global, df_novas], ignore_index=True)
                    
                    salvar_dados(df_global)
                    flash("Ordens cadastradas e salvas com sucesso no Supabase!", "success")
                    
        return redirect(url_for('index', aba='ordens'))

    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1

    f_ordem_id = request.args.get('ordem_id', 'padrao')
    f_juntar = request.args.get('juntar_codigos', '')

    if not df_global.empty:
        status_clean = df_global["Status"].astype(str).str.strip()
        poli_clean = df_global["Policorte"].astype(str).str.strip()
        
        df_global["Prioridade_Ord"] = df_global["Tipo"].astype(str).str.strip().apply(lambda x: 0 if x == "Ordens Criadas" else 1)
        try:
            df_global["ID_num"] = pd.to_numeric(df_global["ID"], errors="coerce")
            ascending_id = False if f_ordem_id == 'decrescente' else True
            
            if f_juntar == 'sim':
                df_sorted = df_global.sort_values(by=["Codigo", "Prioridade_Ord", "ID_num"], ascending=[True, True, ascending_id]).drop(columns=["ID_num", "Prioridade_Ord"])
            else:
                df_sorted = df_global.sort_values(by=["Prioridade_Ord", "ID_num"], ascending=[True, ascending_id]).drop(columns=["ID_num", "Prioridade_Ord"])
        except:
            df_sorted = df_global.sort_values(by=["Prioridade_Ord"], ascending=[True]).drop(columns=["Prioridade_Ord"])

        df_ordens = aplicar_filtros(df_sorted, request.args)
        df_pendentes = aplicar_filtros(df_sorted[status_clean == "Pendente"], request.args)
        df_p1 = aplicar_filtros(df_sorted[(poli_clean == "Policorte 1") & (status_clean == "Em Corte")], request.args)
        df_p2 = aplicar_filtros(df_sorted[(poli_clean == "Policorte 2") & (status_clean == "Em Corte")], request.args)
        df_p3 = aplicar_filtros(df_sorted[(poli_clean == "Policorte 3") & (status_clean == "Em Corte")], request.args)
        df_fin = aplicar_filtros(df_sorted[status_clean == "Finalizado"], request.args)
    else:
        df_ordens = df_pendentes = df_p1 = df_p2 = df_p3 = df_fin = pd.DataFrame()

    ordens_cadastradas_p, page_ordens, total_p_ordens, tot_ordens = paginar_dataframe(df_ordens, page)
    pendentes_p, page_pendentes, total_p_pendentes, tot_pendentes = paginar_dataframe(df_pendentes, page)
    poli1_p, page_p1, total_p_p1, tot_p1 = paginar_dataframe(df_p1, page)
    poli2_p, page_p2, total_p_p2, tot_p2 = paginar_dataframe(df_p2, page)
    poli3_p, page_p3, total_p_p3, tot_p3 = paginar_dataframe(df_p3, page)
    finalizadas_p, page_fin, total_p_fin, tot_fin = paginar_dataframe(df_fin, page)

    # Lógica estruturada para o Painel de Análise de Cargas
    resumo_cargas = []
    ordens_hoje_sem_carga = 0
    total_ordens_criadas_geral = 0
    data_hoje_str = datetime.now().strftime("%d/%m/%Y")

    if not df_global.empty:
        total_ordens_criadas_geral = len(df_global[df_global["Tipo"].astype(str).str.strip() == "Ordens Criadas"])

        df_hoje = df_global[df_global["Data"].astype(str).str.startswith(data_hoje_str)]
        ordens_hoje_sem_carga = len(df_hoje[
            (df_hoje["Carga"].astype(str).str.strip() == "") | 
            (df_hoje["Carga"].astype(str).str.strip().str.lower() == "nan")
        ])

        cargas_unicas = sorted([c for c in df_global["Carga"].astype(str).str.strip().unique() if c and c.lower() != "nan"])
        
        for carga in cargas_unicas:
            df_c = df_global[df_global["Carga"].astype(str).str.strip() == carga]
            tot = len(df_c)
            sep = len(df_c[df_c["Status"].astype(str).str.strip() == "Pendente"])
            corte = len(df_c[df_c["Status"].astype(str).str.strip() == "Em Corte"])
            fin = len(df_c[df_c["Status"].astype(str).str.strip() == "Finalizado"])
            progresso = int((fin / tot) * 100) if tot > 0 else 0
            
            resumo_cargas.append({
                "nome": f"Carga {carga}",
                "total": tot,
                "separacao": sep,
                "em_corte": corte,
                "finalizadas": fin,
                "progresso": progresso
            })
            
        df_avulsa = df_global[(df_global["Carga"].astype(str).str.strip() == "") | (df_global["Tipo"].astype(str).str.strip() == "Ordens Criadas")]
        if not df_avulsa.empty:
            tot_a = len(df_avulsa)
            sep_a = len(df_avulsa[df_avulsa["Status"].astype(str).str.strip() == "Pendente"])
            corte_a = len(df_avulsa[df_avulsa["Status"].astype(str).str.strip() == "Em Corte"])
            fin_a = len(df_avulsa[df_avulsa["Status"].astype(str).str.strip() == "Finalizado"])
            prog_a = int((fin_a / tot_a) * 100) if tot_a > 0 else 0
            
            resumo_cargas.insert(0, {
                "nome": "Ordens Criadas / Avulsas",
                "total": tot_a,
                "separacao": sep_a,
                "em_corte": corte_a,
                "finalizadas": fin_a,
                "progresso": prog_a
            })

    paginacao = {
        'ordens': {'atual': page_ordens, 'total_paginas': total_p_ordens, 'total_itens': tot_ordens},
        'separacao': {'atual': page_pendentes, 'total_paginas': total_p_pendentes, 'total_itens': tot_pendentes},
        'poli1': {'atual': page_p1, 'total_paginas': total_p_p1, 'total_itens': tot_p1},
        'poli2': {'atual': page_p2, 'total_paginas': total_p_p2, 'total_itens': tot_p2},
        'poli3': {'atual': page_p3, 'total_paginas': total_p_p3, 'total_itens': tot_p3},
        'finalizadas': {'atual': page_fin, 'total_paginas': total_p_fin, 'total_itens': tot_fin},
    }

    current_date = datetime.now().strftime("%d/%m/%Y")
    filtros_ativos = {
        'codigo': request.args.get('f_codigo', ''),
        'carga': request.args.get('f_carga', ''),
        'perfil': request.args.get('f_perfil', ''),
        'sobra': request.args.get('f_sobra', ''),
        'data': request.args.get('f_data', ''),
        'ordem_id': f_ordem_id,
        'juntar_codigos': f_juntar
    }

    return render_template('index.html', 
                           ordens_cadastradas=ordens_cadastradas_p, 
                           pendentes=pendentes_p,
                           poli1=poli1_p,
                           poli2=poli2_p,
                           poli3=poli3_p,
                           finalizadas=finalizadas_p,
                           df_global=df_global,
                           resumo_cargas=resumo_cargas,
                           ordens_hoje_sem_carga=ordens_hoje_sem_carga,
                           total_ordens_criadas_geral=total_ordens_criadas_geral,
                           aba_ativa=aba_ativa,
                           paginacao=paginacao,
                           page=page,
                           current_date=current_date,
                           filtros=filtros_ativos)
if __name__ == '__main__':
    app.run(debug=True)