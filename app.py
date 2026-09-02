import io
import pandas as pd
import streamlit as st
from sqlalchemy import text

# Configuración de la página
st.set_page_config(
    page_title="Sistema de Inteligencia Comex",
    page_icon="🚢",
    layout="wide",
)

CLAVE_CORRECTA = "comex2026"

# ---------------------------------------------------------
# 1. CONEXIÓN A POSTGRESQL (SUPABASE)
# ---------------------------------------------------------
# Streamlit busca la URL definida en secrets.toml automáticamente
conn = st.connection("postgres", type="sql")

def inicializar_bd():
  """Crea la tabla en PostgreSQL si no existe y carga datos iniciales."""
  with conn.session as session:
    session.execute(
        text("""
            CREATE TABLE IF NOT EXISTS importaciones (
                id SERIAL PRIMARY KEY,
                fecha TEXT,
                producto TEXT,
                pais_origen TEXT,
                valor_fob NUMERIC,
                flete NUMERIC,
                aduana TEXT
            );
        """)
    )

    # Verificar si está vacía
    res = session.execute(
        text("SELECT COUNT(*) FROM importaciones;")
    ).fetchone()[0]
    if res == 0:
      session.execute(
          text("""
                INSERT INTO importaciones (fecha, producto, pais_origen, valor_fob, flete, aduana)
                VALUES 
                ('2026-01-10', 'Laptops', 'China', 95000.0, 4200.0, 'Buenos Aires'),
                ('2026-01-12', 'Monitores', 'China', 45000.0, 3500.0, 'Buenos Aires'),
                ('2026-01-15', 'Teclados', 'Vietnam', 12000.0, 1100.0, 'Córdoba'),
                ('2026-01-18', 'Laptops', 'EEUU', 80000.0, 2000.0, 'Ezeiza'),
                ('2026-01-20', 'Monitores', 'EEUU', 30000.0, 1800.0, 'Buenos Aires'),
                ('2026-01-22', 'Teclados', 'China', 15000.0, 1200.0, 'Mendoza'),
                ('2026-01-25', 'Celulares', 'China', 120000.0, 5000.0, 'Ezeiza');
            """)
      )
    session.commit()


# Creamos la tabla en Supabase si es la primera vez
inicializar_bd()


# ---------------------------------------------------------
# 2. FUNCIONES DE APOYO
# ---------------------------------------------------------
def convertir_df_a_excel(df_exportar):
  output = io.BytesIO()
  with pd.ExcelWriter(output, engine="openpyxl") as writer:
    df_exportar.to_excel(writer, index=False, sheet_name="Reporte_Comex")
  return output.getvalue()


# ---------------------------------------------------------
# 3. CONTROL DE ACCESO (LOGIN)
# ---------------------------------------------------------
if "autenticado" not in st.session_state:
  st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
  st.title("🔒 Sistema de Comercio Exterior")
  st.subheader("Ingrese su clave de acceso")

  clave = st.text_input("Contraseña:", type="password")
  if st.button("Ingresar"):
    if clave == CLAVE_CORRECTA:
      st.session_state["autenticado"] = True
      st.rerun()
    else:
      st.error("❌ Contraseña incorrecta")
  st.stop()

# ---------------------------------------------------------
# 4. MENÚ Y NAVEGACIÓN LATERAL
# ---------------------------------------------------------
st.sidebar.title("🚢 Navegación")
opcion_menu = st.sidebar.radio(
    "Ir a:", ["📊 Tablero Principal", "➕ Cargar Nuevo Registro"]
)

if st.sidebar.button("Cerrar Sesión"):
  st.session_state["autenticado"] = False
  st.rerun()

# ---------------------------------------------------------
# VISTA 1: TABLERO PRINCIPAL
# ---------------------------------------------------------
if opcion_menu == "📊 Tablero Principal":
  st.title("📊 Monitor de Inteligencia Comercial (Supabase)")

  # Consulta dinámica de productos disponibles con conn.query
  df_prods = conn.query(
      "SELECT DISTINCT producto FROM importaciones;", ttl="1m"
  )
  lista_productos = ["Todos"] + list(df_prods["producto"].dropna().unique())

  st.sidebar.divider()
  st.sidebar.header("🔍 Filtros de Búsqueda")
  prod_sel = st.sidebar.selectbox("Producto:", lista_productos)

  # Consultas según filtro
  if prod_sel == "Todos":
    df_datos = conn.query("SELECT * FROM importaciones;", ttl="1m")
  else:
    df_datos = conn.query(
        "SELECT * FROM importaciones WHERE producto = :prod;",
        params={"prod": prod_sel},
        ttl="1m",
    )

  # Métricas
  col1, col2, col3 = st.columns(3)
  total_fob = df_datos["valor_fob"].sum() if not df_datos.empty else 0
  total_flete = df_datos["flete"].sum() if not df_datos.empty else 0

  col1.metric("Total Importado (FOB)", f"${total_fob:,.0f} USD")
  col2.metric("Total Fletes", f"${total_flete:,.0f} USD")
  col3.metric("Operaciones Encontradas", len(df_datos))

  st.divider()

  if not df_datos.empty:
    st.subheader("Importaciones por País de Origen")
    st.bar_chart(df_datos, x="pais_origen", y="valor_fob")

    st.subheader("Detalle de Registros")
    st.dataframe(df_datos, use_container_width=True)

    st.download_button(
        label="📥 Exportar consulta actual a Excel",
        data=convertir_df_a_excel(df_datos),
        file_name="reporte_comex_supabase.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
    )
  else:
    st.warning("No se encontraron registros con los filtros seleccionados.")

# ---------------------------------------------------------
# VISTA 2: FORMULARIO PARA CARGAR NUEVO REGISTRO
# ---------------------------------------------------------
elif opcion_menu == "➕ Cargar Nuevo Registro":
  st.title("➕ Registrar Nueva Importación en la Nube")

  with st.form("form_registro", clear_on_submit=True):
    col_a, col_b = st.columns(2)

    fecha_inp = col_a.date_input("Fecha de Operación")
    producto_inp = col_a.text_input("Producto (ej: Monitores)")
    pais_inp = col_a.text_input("País de Origen (ej: China)")

    fob_inp = col_b.number_input(
        "Valor FOB (USD)", min_value=0.0, step=500.0, format="%.2f"
    )
    flete_inp = col_b.number_input(
        "Flete (USD)", min_value=0.0, step=100.0, format="%.2f"
    )
    aduana_inp = col_b.text_input("Aduana de Ingreso (ej: Buenos Aires)")

    enviado = st.form_submit_button("Guardar en Supabase")

    if enviado:
      if not producto_inp or not pais_inp:
        st.error(
            "⚠️ Por favor completá al menos el nombre del producto y el país."
        )
      else:
        with conn.session as session:
          session.execute(
              text("""
                        INSERT INTO importaciones (fecha, producto, pais_origen, valor_fob, flete, aduana)
                        VALUES (:fecha, :producto, :pais, :fob, :flete, :aduana);
                    """),
              {
                  "fecha": str(fecha_inp),
                  "producto": producto_inp,
                  "pais": pais_inp,
                  "fob": fob_inp,
                  "flete": flete_inp,
                  "aduana": aduana_inp,
              },
          )
          session.commit()

        st.cache_data.clear()
        st.success(
            f"✅ Registro guardado con éxito en Supabase para '{producto_inp}'."
        )