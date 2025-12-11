import streamlit as st
import json
import os
import io
import pypdf

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Canalhas Brancalonia", layout="wide", page_icon="⚔️")

# --- FUNÇÕES DE DADOS ---
def carregar_dados(arquivo):
    try:
        with open(os.path.join("data", arquivo), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

# Carrega BD
DB_ATRIBUTOS = carregar_dados("atributos.json")
DB_RACAS = carregar_dados("racas.json")
DB_VANTAGENS = carregar_dados("vantagens.json")
DB_EQUIPAMENTO = carregar_dados("equipamento.json")
DB_PERICIAS = carregar_dados("pericias.json")

DADOS_VALOR = {4: "d4", 6: "d6", 8: "d8", 10: "d10", 12: "d12"}

# --- INICIALIZAÇÃO DE ESTADO (SESSION STATE) ---
# O Streamlit roda o script inteiro a cada clique. Precisamos salvar o estado na memória.
if 'atributos' not in st.session_state:
    st.session_state.atributos = {attr: 4 for attr in ["Agilidade", "Astúcia", "Espírito", "Força", "Vigor"]}
if 'pericias' not in st.session_state:
    st.session_state.pericias = {}
    for p in DB_PERICIAS.get("Pericias", []):
        st.session_state.pericias[p["nome"]] = 4 if p.get("basica") else 0
if 'equipamento' not in st.session_state:
    # Formato: {nome_item: quantidade}
    st.session_state.equipamento = {} 
if 'vantagens' not in st.session_state:
    st.session_state.vantagens = []
if 'complicacoes' not in st.session_state:
    st.session_state.complicacoes = []
if 'raca' not in st.session_state:
    st.session_state.raca = "Humano"

# --- LÓGICA DE CÁLCULO (Mesma do Desktop) ---
def recalcular_pontos():
    # 1. Complicações (Max 4 pts)
    pts_compl = 0
    for c in st.session_state.complicacoes:
        tipo = next((x['tipo'] for x in DB_VANTAGENS['Desvantagens'] if x['nome'] == c), "Menor")
        pts_compl += 2 if "Maior" in tipo else 1
    pts_uteis = min(pts_compl, 4)

    # 2. Vantagens (2 pts cada)
    custo_vant = len(st.session_state.vantagens) * 2

    # 3. Atributos Extras
    gasto_attr_base = 0
    mods_raciais = DB_RACAS[st.session_state.raca].get("modificadores", {})
    
    for attr, val in st.session_state.atributos.items():
        base = 4 + (mods_raciais.get(attr, 0) * 2)
        if val < base: # Corrige se estiver abaixo do mínimo racial
            st.session_state.atributos[attr] = base
            val = base
        steps = (val - base) // 2
        gasto_attr_base += steps

    pontos_base_gastos = min(gasto_attr_base, 5)
    extras = max(0, gasto_attr_base - 5)
    custo_attr_extra = extras * 2

    saldo = pts_uteis - custo_vant - custo_attr_extra
    
    # Perícias
    gasto_pericias = 0
    for nome, valor in st.session_state.pericias.items():
        if valor > 0:
            link = next((p['atributo'] for p in DB_PERICIAS["Pericias"] if p['nome'] == nome), "Agilidade")
            val_attr = st.session_state.atributos.get(link, 4)
            is_core = any(p['nome'] == nome and p.get('basica') for p in DB_PERICIAS["Pericias"])
            
            curr = 4
            custo_p = 0
            while curr <= valor:
                if curr == 4 and is_core: pass
                else: custo_p += 1 if curr <= val_attr else 2
                curr += 2
            gasto_pericias += custo_p

    return {
        "saldo": saldo, 
        "attr_base": pontos_base_gastos, 
        "pericias_gastas": gasto_pericias,
        "dinheiro_gasto": sum([
            next((i['custo'] for cat in DB_EQUIPAMENTO.values() for i in cat if i['nome'] == item), 0) * qtd
            for item, qtd in st.session_state.equipamento.items()
        ])
    }

# --- FUNÇÃO DE EXPORTAR PDF (Para Memória) ---
def gerar_pdf_bytes():
    arquivo_base = os.path.join("data", "brancasheet.pdf")
    if not os.path.exists(arquivo_base):
        return None

    reader = pypdf.PdfReader(arquivo_base)
    writer = pypdf.PdfWriter()
    writer.append_pages_from_reader(reader)

    if "/AcroForm" in reader.root_object:
        writer.root_object[pypdf.generic.NameObject("/AcroForm")] = reader.root_object["/AcroForm"]

    fields = {}
    fields["Nome"] = "Canalha Mobile"
    fields["Raça"] = st.session_state.raca
    
    for attr, val in st.session_state.atributos.items():
        fields[f"{attr}_d{val}"] = "/Yes"

    ativos = [k for k, v in st.session_state.pericias.items() if v > 0]
    for i, skill in enumerate(ativos[:20]):
        fields[f"Perícia_{i+1}"] = skill
        fields[f"Perícia_{i+1}_d{st.session_state.pericias[skill]}"] = "/Yes"

    for i, v in enumerate(st.session_state.vantagens[:10]):
        if i < 4: fields[f"Vantagem_{i+1}"] = v
        elif i == 4: fields["Vantagem_5"] = v
        else: fields[f"Vantagem_N_{i-4}"] = v

    for i, c in enumerate(st.session_state.complicacoes[:4]):
        fields[f"Complicação_{i+1}"] = c

    lista_equip = []
    for item, qtd in st.session_state.equipamento.items():
        if qtd > 0: lista_equip.append(f"{qtd}x {item}" if qtd > 1 else item)
    
    for i, item in enumerate(lista_equip[:18]):
        fields[f"Equipamento_{i+1}"] = item
    
    stats = recalcular_pontos()
    restante = 500 - stats['dinheiro_gasto']
    if len(lista_equip) < 18:
        fields[f"Equipamento_{len(lista_equip)+1}"] = f"--- Dinheiro: ${restante} ---"

    for page in writer.pages:
        writer.update_page_form_field_values(page, fields)

    # Salva na memória RAM (BytesIO) em vez de disco
    buffer = io.BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    return buffer

# --- INTERFACE VISUAL ---
st.title("🛡️ Gerador de Canalhas (Brancalonia)")

# Menu Lateral (Raça e Resumo)
with st.sidebar:
    st.header("1. Origem")
    nova_raca = st.selectbox("Escolha a Raça", list(DB_RACAS.keys()), index=list(DB_RACAS.keys()).index(st.session_state.raca))
    
    # Se mudou a raça, reseta atributos para evitar bug
    if nova_raca != st.session_state.raca:
        st.session_state.raca = nova_raca
        st.session_state.atributos = {attr: 4 for attr in st.session_state.atributos}
        st.rerun()

    desc = DB_RACAS[st.session_state.raca]
    st.info(desc.get("descricao", ""))
    st.caption("Bônus: " + ", ".join([f"{k}: {v}" for k,v in desc.get("bonus", {}).items()]))

    st.divider()
    
    # Resumo de Pontos (Sempre visível)
    stats = recalcular_pontos()
    
    col1, col2 = st.columns(2)
    col1.metric("Attr Base", f"{stats['attr_base']}/5")
    col2.metric("Saldo Criação", stats['saldo'], delta_color="normal" if stats['saldo'] >= 0 else "inverse")
    
    pts_pericia = DB_PERICIAS.get("pontos_iniciais", 12)
    st.metric("Pts Perícia", f"{pts_pericia - stats['pericias_gastas']}/{pts_pericia}")
    
    st.metric("Dinheiro", f"${500 - stats['dinheiro_gasto']}", delta_color="normal" if 500 >= stats['dinheiro_gasto'] else "inverse")

    # Botão de Download PDF
    pdf_bytes = gerar_pdf_bytes()
    if pdf_bytes:
        st.download_button("💾 Baixar Ficha PDF", data=pdf_bytes, file_name="meu_canalha.pdf", mime="application/pdf")
    else:
        st.error("Erro ao gerar PDF (Arquivo base não encontrado)")

# Abas Principais
tab1, tab2, tab3, tab4 = st.tabs(["Atributos", "Perícias", "Vantagens", "Equipamento"])

with tab1:
    st.subheader("Atributos")
    cols = st.columns(5)
    for i, (attr, val) in enumerate(st.session_state.atributos.items()):
        with cols[i]:
            st.markdown(f"**{attr}**")
            # Botões +/-
            c1, c2, c3 = st.columns([1, 2, 1])
            if c1.button("➖", key=f"dec_{attr}"):
                if st.session_state.atributos[attr] > 4:
                    st.session_state.atributos[attr] -= 2
                    st.rerun()
            
            c2.markdown(f"<h3 style='text-align: center'>{DADOS_VALOR[val]}</h3>", unsafe_allow_html=True)
            
            if c3.button("➕", key=f"inc_{attr}"):
                if st.session_state.atributos[attr] < 12:
                    st.session_state.atributos[attr] += 2
                    st.rerun()

with tab2:
    st.subheader("Perícias")
    st.caption("Perícias marcadas com * são básicas.")
    
    lista_pericias = sorted(DB_PERICIAS.get("Pericias", []), key=lambda x: x['nome'])
    
    for p in lista_pericias:
        nome = p['nome']
        link = p['atributo']
        basica = p.get('basica', False)
        val = st.session_state.pericias[nome]
        
        col_nome, col_btn_menos, col_val, col_btn_mais = st.columns([4, 1, 2, 1])
        
        with col_nome:
            st.write(f"{nome} ({link[:3]}) {'*' if basica else ''}")
        
        with col_btn_menos:
            if st.button("➖", key=f"p_dec_{nome}"):
                niveis = [0, 4, 6, 8, 10, 12]
                idx = niveis.index(val)
                if idx > 0:
                    novo = niveis[idx-1]
                    if not (basica and novo == 0):
                        st.session_state.pericias[nome] = novo
                        st.rerun()

        with col_val:
            st.markdown(f"<div style='text-align:center'><b>{DADOS_VALOR.get(val, '--')}</b></div>", unsafe_allow_html=True)

        with col_btn_mais:
            if st.button("➕", key=f"p_inc_{nome}"):
                niveis = [0, 4, 6, 8, 10, 12]
                idx = niveis.index(val)
                if idx < len(niveis) - 1:
                    st.session_state.pericias[nome] = niveis[idx+1]
                    st.rerun()
        st.divider()

with tab3:
    col_c, col_v = st.columns(2)
    
    with col_c:
        st.subheader("Complicações")
        opcoes_c = [c['nome'] for c in DB_VANTAGENS.get("Desvantagens", [])]
        st.session_state.complicacoes = st.multiselect("Selecione (Ganha pts):", options=opcoes_c, default=st.session_state.complicacoes)
        
    with col_v:
        st.subheader("Vantagens")
        opcoes_v = [v['nome'] for v in DB_VANTAGENS.get("Vantagens", [])]
        st.session_state.vantagens = st.multiselect("Selecione (Gasta 2 pts):", options=opcoes_v, default=st.session_state.vantagens)

with tab4:
    st.subheader("Equipamento")
    
    for cat, itens in DB_EQUIPAMENTO.items():
        with st.expander(f"📦 {cat}"):
            for item in itens:
                nome = item['nome']
                custo = item.get('custo', 0)
                if isinstance(custo, str): custo = 0
                
                c_chk, c_qtd = st.columns([3, 1])
                
                # Checkbox lógica
                tem_item = nome in st.session_state.equipamento
                selecionado = c_chk.checkbox(f"{nome} (${custo})", value=tem_item, key=f"chk_{nome}")
                
                if selecionado:
                    qtd = c_qtd.number_input("Qtd", min_value=1, value=st.session_state.equipamento.get(nome, 1), key=f"qtd_{nome}")
                    st.session_state.equipamento[nome] = qtd
                elif nome in st.session_state.equipamento:
                     del st.session_state.equipamento[nome]