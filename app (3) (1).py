%%writefile app.py
import streamlit as st
import pandas as pd
import plotly.express as px

# --- Configurações Iniciais da Página ---
st.set_page_config(
    page_title="Dashboard de Cartórios",
    layout="wide"
)

# --- Funções de Carregamento de Dados ---

@st.cache_data
def carregar_cadastro():
    """Carrega a lista completa de cartórios."""
    try:
        df = pd.read_csv("cadastro_cartorios.csv")
        return df
    except Exception as e:
        # Retorna vazio para não quebrar, o st.error avisa depois
        return pd.DataFrame()

@st.cache_data
def carregar_e_limpar_financeiro():
    """Carrega os dados financeiros direto do Google Drive."""
    
    # Link de download direto
    URL_FINANCEIRO = "https://drive.google.com/uc?export=download&id=110srBvTbBOWr5ii6atT2zv3PMh5bXML_"
    
    try:
        df = pd.read_csv(URL_FINANCEIRO)
    except Exception as e:
        st.error(f"Erro ao baixar do Google Drive: {e}")
        return pd.DataFrame()

    # Limpeza dos dados
    if 'Valor arrecadação' in df.columns:
        coluna_valores = df['Valor arrecadação'].astype(str).str.strip()
        coluna_valores = coluna_valores.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        df['Valor arrecadação'] = pd.to_numeric(coluna_valores, errors='coerce')
    
    if 'Dat. início do período' in df.columns:
        df['Dat. início do período'] = pd.to_datetime(df['Dat. início do período'], format='%d/%m/%Y', errors='coerce')
    
    df.dropna(subset=['Valor arrecadação', 'Dat. início do período'], inplace=True)
    df = df[df['Valor arrecadação'] > 0]
    
    # CORREÇÃO: Ordenação por data
    df = df.sort_values(by='Dat. início do período')
    
    return df

# --- Carregamento Inicial ---
try:
    # Mensagem simples para não travar visualmente
    df_cartorios = carregar_cadastro()
    df_financeiro_completo = carregar_e_limpar_financeiro()
    
    if df_financeiro_completo.empty or df_cartorios.empty:
        st.error("Faltam arquivos. Verifique se 'cadastro_cartorios.csv' foi enviado.")
        st.stop() 
            
except Exception as e:
    st.error(f"Erro crítico: {e}")
    st.stop()

# --- BARRA LATERAL ---
st.sidebar.header("Configurações de Análise")

ufs_disponiveis = sorted(df_cartorios["UF"].unique()) if not df_cartorios.empty else []
estado_selecionado = st.sidebar.selectbox("1. Selecione o Estado:", ufs_disponiveis)

modo_analise = st.sidebar.radio(
    "Nível de Detalhe:",
    ("Visão Geral do Estado", "Cartório Específico")
)

cartorio_selecionado_nome = None
cns_para_analise = []
info_cartorio = None

if modo_analise == "Cartório Específico":
    cidades_no_estado = sorted(df_cartorios[df_cartorios["UF"] == estado_selecionado]["Cidade"].unique())
    cidade_selecionada = st.sidebar.selectbox("2. Selecione a Cidade:", cidades_no_estado)
    
    cartorios_na_cidade = df_cartorios[df_cartorios["Cidade"] == cidade_selecionada]
    cartorio_selecionado_nome = st.sidebar.selectbox("3. Selecione o Cartório:", cartorios_na_cidade["Denominação"].unique())
    
    if cartorio_selecionado_nome:
        info_cartorio = df_cartorios[df_cartorios["Denominação"] == cartorio_selecionado_nome].iloc[0]
        cns_para_analise = [info_cartorio['CNS']]
else:
    cns_para_analise = df_cartorios[df_cartorios["UF"] == estado_selecionado]['CNS'].unique().tolist()
    st.sidebar.info(f"Analisando {len(cns_para_analise)} cartórios em {estado_selecionado}.")

# --- PÁGINA PRINCIPAL ---
st.title(f"📊 Painel de Análise - {estado_selecionado}")

if modo_analise == "Cartório Específico" and not cartorio_selecionado_nome:
    st.warning("👈 Por favor, selecione um cartório na barra lateral.")
    st.stop()

if modo_analise == "Cartório Específico" and info_cartorio is not None:
    st.markdown(f"### Detalhes: {info_cartorio['Denominação']}")
    col1, col2, col3 = st.columns(3)
    col1.metric("Cidade", info_cartorio['Cidade'])
    col2.metric("Status", info_cartorio['Status'])
    col3.metric("Tipo", info_cartorio['Tipo'])
    st.markdown("---")

# --- PROCESSAMENTO ---
df_financeiro_filtrado = df_financeiro_completo[df_financeiro_completo['CNS'].isin(cns_para_analise)]

if not df_financeiro_filtrado.empty:
    df_filtrado_agregado = df_financeiro_filtrado.groupby('Dat. início do período')['Valor arrecadação'].sum().reset_index()
    df_filtrado_agregado.rename(columns={'Dat. início do período': 'Mês'}, inplace=True)
    
    # CORREÇÃO: Ordenação da tabela agregada
    df_filtrado_agregado = df_filtrado_agregado.sort_values(by='Mês')
else:
    df_filtrado_agregado = pd.DataFrame()

# --- EXIBIÇÃO ---
titulo_secao = "Análise Financeira Global" if modo_analise == "Visão Geral do Estado" else "Análise Financeira Individual"
st.header(titulo_secao)

if not df_filtrado_agregado.empty and len(df_filtrado_agregado) >= 1:
    ultimo_valor = df_filtrado_agregado['Valor arrecadação'].iloc[-1]
    
    delta_val = None
    if len(df_filtrado_agregado) >= 2:
        penultimo_valor = df_filtrado_agregado['Valor arrecadação'].iloc[-2]
        variacao = ultimo_valor - penultimo_valor
        delta_val = f"R$ {variacao:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    valor_formatado = f"R$ {ultimo_valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    st.metric(
        label=f"Arrecadação Total em {df_filtrado_agregado['Mês'].iloc[-1].strftime('%m/%Y')}",
        value=valor_formatado,
        delta=delta_val
    )

    st.subheader("Evolução da Arrecadação Mensal")
    fig = px.line(
        df_filtrado_agregado, 
        x='Mês', 
        y='Valor arrecadação',
        title='Histórico de Arrecadação',
        markers=True,
        template="plotly_white"
    )
    fig.update_layout(yaxis_tickprefix = 'R$ ')
    fig.update_xaxes(dtick="M1", tickformat="%b/%Y")
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("Ver tabela de dados"):
        df_tabela = df_filtrado_agregado.copy()
        df_tabela['Valor arrecadação'] = df_tabela['Valor arrecadação'].apply(lambda x: f"R$ {x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        st.dataframe(df_tabela)
else:
    st.warning(f"Não foram encontrados dados financeiros para {estado_selecionado}.")
