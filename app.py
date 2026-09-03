from datetime import datetime
import pandas as pd
from supabase import create_client
import streamlit as st

st.set_page_config(
    page_title="Comex BI - Sistema Inteligente", layout="wide"
)

# --- 1. CONFIGURACIÓN DE CONEXIÓN A SUPABASE ---
try:
  supabase_url = st.secrets["supabase"]["url"]
  supabase_key = st.secrets["supabase"]["key"]
  supabase = create_client(supabase_url, supabase_key)
except Exception as e:
  st.error(
      "⚠️ Error de configuración: Faltan las credenciales de Supabase en"
      " secrets.toml"
  )
  supabase = None


# --- 2. FUNCIÓN PARA OBTENER CONFIGURACIÓN DEL CLIENTE ---
def obtener_configuracion_cliente():
  if supabase is None:
    return {
        "empresa_nombre": "Empresa Demo",
        "ver_modulo_financiero": True,
        "ver_modulo_logistico": True,
        "ver_simulador": True,
        "alerta_margen_limite": 15.0,
    }

  try:
    response = supabase.table("configuracion_cliente").select("*").execute()
    if response.data and len(response.data) > 0:
      return response.data[0]
  except Exception:
    pass

  return {
      "empresa_nombre": "Mi Empresa Comex",
      "ver_modulo_financiero": True,
      "ver_modulo_logistico": True,
      "ver_simulador": True,
      "alerta_margen_limite": 15.0,
  }


config_cliente = obtener_configuracion_cliente()

st.title(f"📊 Comex BI — {config_cliente.get('empresa_nombre', 'Plataforma')}")

# --- 3. MÓDULO DE CARGA Y MAPEO DINÁMICO ---
st.sidebar.header("📁 Gestión de Datos")
archivo_subido = st.sidebar.file_uploader(
    "Subir Excel de la Empresa", type=["xlsx", "xls"]
)

st.sidebar.divider()
st.sidebar.subheader("⚙️ Configuración Activa")
st.sidebar.text(
    f"Módulo Financiero: {'✅' if config_cliente.get('ver_modulo_financiero') else '❌'}"
)
st.sidebar.text(
    f"Módulo Logístico: {'✅' if config_cliente.get('ver_modulo_logistico') else '❌'}"
)
st.sidebar.text(
    f"Simulador: {'✅' if config_cliente.get('ver_simulador') else '❌'}"
)

# Si el usuario sube un archivo nuevo, procesamos el mapeo
if archivo_subido is not None:
  df_original = pd.read_excel(archivo_subido)

  st.subheader("1. Vista Previa del Archivo Original")
  st.dataframe(df_original.head(), use_container_width=True)

  st.divider()
  st.subheader("2. Adaptación y Mapeo de Columnas")
  st.info(
      "El sistema detectó las siguientes columnas en tu archivo. Por favor,"
      " vinculalas con los estándares del sistema:"
  )

  columnas_excel = df_original.columns.tolist()


  def buscar_sugerencia(lista, posibles_nombres):
    for col in lista:
      if any(p in col.lower() for p in posibles_nombres):
        return col
    return lista[0] if lista else None


  c1, c2 = st.columns(2)

  with c1:
    col_fecha = st.selectbox(
        "Columna de Fecha:",
        columnas_excel,
        index=columnas_excel.index(
            buscar_sugerencia(columnas_excel, ["fecha", "date", "f."])
        ),
    )
    col_producto = st.selectbox(
        "Columna de Producto / Descripción:",
        columnas_excel,
        index=columnas_excel.index(
            buscar_sugerencia(
                columnas_excel, ["producto", "item", "descripcion", "sku"]
            )
        ),
    )
    col_cantidad = st.selectbox(
        "Columna de Cantidad:",
        columnas_excel,
        index=columnas_excel.index(
            buscar_sugerencia(columnas_excel, ["cantidad", "cant", "qty"])
        ),
    )

  with c2:
    col_valor = st.selectbox(
        "Columna de Valor / FOB:",
        columnas_excel,
        index=columnas_excel.index(
            buscar_sugerencia(columnas_excel, ["fob", "valor", "precio", "usd"])
        ),
    )
    col_proveedor = st.selectbox(
        "Columna de Proveedor:",
        columnas_excel,
        index=columnas_excel.index(
            buscar_sugerencia(
                columnas_excel, ["proveedor", "supplier", "vendor"]
            )
        ),
    )
    col_destino = st.selectbox(
        "Columna de Destino / País:",
        columnas_excel,
        index=columnas_excel.index(
            buscar_sugerencia(columnas_excel, ["destino", "pais", "country"])
        ),
    )

  if st.button("🚀 Procesar y Guardar en Supabase", type="primary"):
    df_estandarizado = pd.DataFrame()
    df_estandarizado["fecha"] = pd.to_datetime(
        df_original[col_fecha], errors="coerce"
    )
    df_estandarizado["producto"] = df_original[col_producto].astype(str)
    df_estandarizado["cantidad"] = pd.to_numeric(
        df_original[col_cantidad], errors="coerce"
    ).fillna(0)
    df_estandarizado["valor_fob"] = pd.to_numeric(
        df_original[col_valor], errors="coerce"
    ).fillna(0)
    df_estandarizado["proveedor"] = df_original[col_proveedor].astype(str)
    df_estandarizado["destino"] = df_original[col_destino].astype(str)
    df_estandarizado["costo_logistico"] = 0.0

    # Guardamos en Supabase
    if supabase is not None:
      try:
        registros = []
        for _, row in df_estandarizado.iterrows():
          fecha_str = (
              row["fecha"].strftime("%Y-%m-%d")
              if pd.notnull(row["fecha"])
              else None
          )
          registros.append({
              "fecha": fecha_str,
              "producto": row["producto"],
              "cantidad": float(row["cantidad"]),
              "valor_fob": float(row["valor_fob"]),
              "destino": row["destino"],
              "proveedor": row["proveedor"],
              "costo_logistico": float(row["costo_logistico"]),
          })
        supabase.table("datos_comex").insert(registros).execute()
        st.success("¡Datos guardados y sincronizados en Supabase!")
      except Exception as e:
        st.error(f"Error al guardar en la base de datos: {e}")

    # Guardamos en sesión
    st.session_state["df_comex"] = df_estandarizado
    st.rerun()

# --- 4. DASHBOARD Y VISUALIZACIÓN DE DATOS (SI YA HAY DATOS CARGADOS) ---
if "df_comex" in st.session_state:
  df = st.session_state["df_comex"]

  st.divider()
  st.subheader("📈 Tablero de Control y Analítica")

  # Filtro de fechas en barra lateral
  st.sidebar.divider()
  st.sidebar.subheader("📅 Filtrar por Período")

  df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
  min_f = (
      df["fecha"].min().date()
      if pd.notnull(df["fecha"].min())
      else datetime.today().date()
  )
  max_f = (
      df["fecha"].max().date()
      if pd.notnull(df["fecha"].max())
      else datetime.today().date()
  )

  rango_fechas = st.sidebar.date_input(
      "Rango de Fechas", value=(min_f, max_f), min_value=min_f, max_value=max_f
  )

  if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
    inicio, fin = rango_fechas
    df_filtrado = df[
        (df["fecha"].dt.date >= inicio) & (df["fecha"].dt.date <= fin)
    ]
  else:
    df_filtrado = df

  # Construcción de solapas dinámicas según configuración de Supabase
  nombres_solapas = []
  if config_cliente.get("ver_modulo_financiero", True):
    nombres_solapas.append("📊 Resumen Ejecutivo (KPIs)")
  if config_cliente.get("ver_modulo_logistico", True):
    nombres_solapas.append("💰 Costos y Proveedores")
  if config_cliente.get("ver_simulador", True):
    nombres_solapas.append("🎛️ Simulador What-If")

  if nombres_solapas:
    solapas = st.tabs(nombres_solapas)
    indice_tab = 0

    if config_cliente.get("ver_modulo_financiero", True):
      with solapas[indice_tab]:
        st.subheader("Indicadores Clave del Período")
        col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)

        total_fob = df_filtrado["valor_fob"].sum()
        total_operaciones = len(df_filtrado)
        cantidad_total = df_filtrado["cantidad"].sum()
        ticket_promedio = (
            total_fob / total_operaciones if total_operaciones > 0 else 0
        )

        col_kpi1.metric("Gasto Total FOB", f"${total_fob:,.2f}")
        col_kpi2.metric("Total Operaciones", f"{total_operaciones:,}")
        col_kpi3.metric("Unidades Movidas", f"{cantidad_total:,.0f}")
        col_kpi4.metric("Ticket Promedio", f"${ticket_promedio:,.2f}")

        st.markdown("---")
        st.dataframe(df_filtrado, use_container_width=True)
      indice_tab += 1

    if config_cliente.get("ver_modulo_logistico", True):
      with solapas[indice_tab]:
        st.subheader("Análisis de Proveedores y Destinos")
        col_l1, col_l2 = st.columns(2)

        with col_l1:
          st.markdown("**Gasto por Proveedor**")
          if "proveedor" in df_filtrado.columns:
            prov_gasto = (
                df_filtrado.groupby("proveedor")["valor_fob"]
                .sum()
                .reset_index()
            )
            st.bar_chart(prov_gasto.set_index("proveedor"))

        with col_l2:
          st.markdown("**Volumen por Destino / País**")
          if "destino" in df_filtrado.columns:
            dest_gasto = (
                df_filtrado.groupby("destino")["valor_fob"].sum().reset_index()
            )
            st.bar_chart(dest_gasto.set_index("destino"))
      indice_tab += 1

    if config_cliente.get("ver_simulador", True):
      with solapas[indice_tab]:
        st.subheader("Simulador de Impacto Logístico y Cambiario")
        st.info("Mové los controles para simular variaciones en los costos.")
        total_fob_act = df_filtrado["valor_fob"].sum()
        porcentaje_flete = st.slider(
            "Variación estimada de Fletes / Costos (%)", -20, 50, 0
        )
        fob_simulado = total_fob_act * (1 + porcentaje_flete / 100)
        st.metric(
            "Gasto Total Simulado",
            f"${fob_simulado:,.2f}",
            delta=f"{porcentaje_flete}%",
        )
      indice_tab += 1

elif archivo_subido is None:
  st.warning("⚠️ Por favor, subí un archivo Excel en la barra lateral para comenzar.")