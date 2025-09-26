import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from math import ceil

load_dotenv()

# 🔑 Conectar ao Supabase
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
if not url or not key:
    st.stop()
supabase: Client = create_client(url, key)

st.title("📊 Upload e Análise de Planilhas com Supabase")

uploaded_file = st.file_uploader("Envie sua planilha (Excel ou CSV)", type=["xlsx", "xls", "csv"])

def ler_planilha(f):
    if f.name.lower().endswith(".csv"):
        return pd.read_csv(f)
    return pd.read_excel(f)

if uploaded_file:
    df = ler_planilha(uploaded_file)

    # 1) Normalizar cabeçalhos
    df.columns = df.columns.str.strip().str.lower()

    # 2) Mapear possíveis variações de nomes (ajuste se precisar)
    mapa_colunas = {
        "nome": ["nome", "name"],
        "idade": ["idade", "anos", "idade (anos)"],
        "cidade": ["cidade", "municipio", "município"],
    }
    # criar um dict {col_normalizada: coluna_existente_no_df}
    col_map_efetivo = {}
    for alvo, aliases in mapa_colunas.items():
        for a in aliases:
            if a in df.columns:
                col_map_efetivo[alvo] = a
                break

    # 3) Selecionar somente as colunas que existem
    cols_validas = [c for c in ["nome", "idade", "cidade"] if c in col_map_efetivo]
    if not cols_validas:
        st.error("❌ A planilha não contém nenhuma das colunas esperadas: nome, idade, cidade.")
        st.stop()

    df_sel = df[[col_map_efetivo[c] for c in cols_validas]].rename(columns={col_map_efetivo[c]: c for c in cols_validas})

    # 4) Limpar linhas totalmente vazias nessas colunas
    df_sel = df_sel.dropna(how="all", subset=cols_validas)

    # 5) Tipos e valores
    if "idade" in df_sel.columns:
        df_sel["idade"] = pd.to_numeric(df_sel["idade"], errors="coerce")  # vira float/NaN
        df_sel["idade"] = df_sel["idade"].astype("Int64")                  # inteiro nulo (pandas)
    # Substituir NaN por None para enviar ao PostgREST
    df_sel = df_sel.where(pd.notnull(df_sel), None)

    # 6) Transformar em registros e remover dicionários vazios
    registros = [r for r in df_sel.to_dict(orient="records") if any(v is not None for v in r.values())]
    if not registros:
        st.error("❌ Não há registros válidos para inserir após a limpeza dos dados.")
        st.stop()

    # 7) Limpar a tabela (opcional) e inserir em lotes
    supabase.table("planilhas").delete().neq("id", 0).execute()

    lote = 500  # ajuste se quiser
    total = len(registros)
    for i in range(0, total, lote):
        chunk = registros[i:i+lote]
        supabase.table("planilhas").insert(chunk).execute()

    st.success(f"✅ {total} registro(s) carregado(s) e salvo(s) no banco!")

# 📑 Mostrar dados do Supabase
st.subheader("📑 Dados armazenados")
response = supabase.table("planilhas").select("*").execute()
dados = response.data or []
if dados:
    df_banco = pd.DataFrame(dados)
    st.dataframe(df_banco)
    if "idade" in df_banco.columns:
        try:
            media_idade = pd.to_numeric(df_banco["idade"], errors="coerce").mean()
            if pd.notnull(media_idade):
                st.metric("📈 Média de Idade", f"{media_idade:.1f}")
        except Exception:
            pass
else:
    st.info("Nenhum dado no banco ainda. Faça upload de uma planilha.")
