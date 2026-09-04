from datetime import datetime, timedelta
import io
import pandas as pd
from supabase import create_client
import streamlit as st

st.set_page_config(page_title="Comex BI — Enterprise", layout="wide")

# --- TIEMPO MÁXIMO DE INACTIVIDAD (Ej: 4 horas) ---
TIEMPO_INACTIVIDAD_HORAS = 4

# --- 1. CONFIGURACIÓN DE CONEXIÓN A SUPABASE ---
try:
    supabase_url = st.secrets["supabase"]["url"]
    supabase_key = st.secrets["supabase"]["key"]
except Exception:
    supabase_url = "https://dqknwcocdpcnnhumtntv.supabase.co"
    supabase_key = "sb_publishable_p_t8Ut4iU02WEflHZZRigQ_g11xnG4z"

try:
    supabase = create_client(supabase_url, supabase_key)
except Exception as e:
    st.error(f"⚠️ Error al conectar con Supabase: {e}")
    supabase = None

# --- 2. CONTROL DE SESIÓN, PERSISTENCIA (QUERY PARAMS) E INACTIVIDAD ---
if "user" not in st.session_state:
    st.session_state.user = None
if "rol_usuario" not in st.session_state:
    st.session_state.rol_usuario = "visor"
if "empresa_usuario" not in st.session_state:
    st.session_state.empresa_usuario = "General"
if "ultimo_acceso" not in st.session_state:
    st.session_state.ultimo_acceso = datetime.now()
if "modo_recuperacion" not in st.session_state:
    st.session_state.modo_recuperacion = False

# Recuperar sesión persistente mediante query_params para evitar que se caiga al recargar (F5)
query_params = st.query_params
if st.session_state.user is None and "session_token" in query_params:
    token_guardado = query_params["session_token"]
    if token_guardado and supabase is not None:
        try:
            res_session = supabase.auth.get_user(token_guardado)
            if res_session and res_session.user:
                st.session_state.user = res_session.user
                user_email = st.session_state.user.email
                st.session_state.ultimo_acceso = datetime.now()
                
                res_perfil = supabase.table("user_profiles").select("empresa, Rol").eq("email", user_email).execute()
                if res_perfil.data and len(res_perfil.data) > 0:
                    st.session_state.empresa_usuario = res_perfil.data[0].get("empresa", "COMEX_Sistema")
                    rol_db = str(res_perfil.data[0].get("Rol", "")).strip().lower()
                    if "admin" in rol_db:
                        st.session_state.rol_usuario = "admin"
                    elif "operativ" in rol_db:
                        st.session_state.rol_usuario = "operativo"
                    else:
                        st.session_state.rol_usuario = "visor"
                else:
                    st.session_state.empresa_usuario = "COMEX_Sistema"
                    st.session_state.rol_usuario = "admin"
        except Exception:
            st.query_params.clear()

# Control de inactividad por tiempo
if st.session_state.user is not None:
    tiempo_transcurrido = datetime.now() - st.session_state.ultimo_acceso
    if tiempo_transcurrido > timedelta(hours=TIEMPO_INACTIVIDAD_HORAS):
        st.session_state.user = None
        if "session_token" in st.query_params:
            del st.query_params["session_token"]
        st.warning("⏱️ Su sesión ha expirado por inactividad prolongada. Por favor, vuelva a iniciar sesión.")
        st.rerun()
    else:
        st.session_state.ultimo_acceso = datetime.now()

# Pantalla de Login si no hay usuario autenticado
if st.session_state.user is None:
    st.subheader("🔐 Iniciar Sesión — Comex BI Enterprise")

    if not st.session_state.modo_recuperacion:
        with st.form("form_login"):
            email = st.text_input("Correo electrónico")
            password = st.text_input("Contraseña", type="password")
            submit_btn = st.form_submit_button("Entrar")

        if submit_btn:
            try:
                res = supabase.auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                st.session_state.user = res.user
                st.session_state.ultimo_acceso = datetime.now()
                
                if res.session and res.session.access_token:
                    st.query_params["session_token"] = res.session.access_token

                user_email = st.session_state.user.email

                res_perfil = (
                    supabase.table("user_profiles")
                    .select("empresa, Rol")
                    .eq("email", user_email)
                    .execute()
                )

                if res_perfil.data and len(res_perfil.data) > 0:
                    st.session_state.empresa_usuario = res_perfil.data[0].get("empresa", "COMEX_Sistema")
                    rol_db = str(res_perfil.data[0].get("Rol", "")).strip().lower()

                    if "admin" in rol_db:
                        st.session_state.rol_usuario = "admin"
                    elif "operativ" in rol_db:
                        st.session_state.rol_usuario = "operativo"
                    else:
                        st.session_state.rol_usuario = "visor"
                else:
                    st.session_state.empresa_usuario = "COMEX_Sistema"
                    st.session_state.rol_usuario = "admin"

                st.success("¡Ingreso exitoso!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al iniciar sesión: Verificá tus datos. Detalle: {e}")

        st.divider()
        if st.button("🔑 ¿Olvidaste tu contraseña?"):
            st.session_state.modo_recuperacion = True
            st.rerun()

    else:
        st.markdown("### Recuperar Contraseña")
        st.markdown("Ingresá tu correo electrónico y te enviaremos un enlace para blanquear tu clave de acceso.")
        
        with st.form("form_recuperar"):
            email_recu = st.text_input("Correo electrónico registrado")
            btn_enviar_recu = st.form_submit_button("Enviar enlace de recuperación")
            
        if btn_enviar_recu:
            if not email_recu:
                st.error("Por favor, ingresá un correo electrónico válido.")
            else:
                try:
                    # Supabase envía el correo de blanqueo automáticamente
                    supabase.auth.reset_password_for_email(email_recu)
                    st.success("¡Listo! Si el correo está registrado, se te ha enviado un enlace para restablecer tu contraseña.")
                except Exception as e:
                    st.error(f"Ocurrió un error al intentar enviar el correo: {e}")
                    
        if st.button("Volver al Login"):
            st.session_state.modo_recuperacion = False
            st.rerun()

    st.stop()

if "user" in st.session_state and st.session_state.user is not None:
    if getattr(st.session_state.user, "email", "") == "tomasricordi5@gmail.com":
        st.session_state.rol_usuario = "admin"


# --- 3. CARGA DE CONFIGURACIÓN Y DATOS PERSISTENTES ---
def obtener_configuracion_cliente():
    if supabase is None or "empresa_usuario" not in st.session_state:
        return {
            "empresa_nombre": "Empresa Demo",
            "ver_modulo_financiero": True,
            "ver_modulo_logistico": True,
            "ver_simulador": True,
            "alerta_margen_limite": 15.0,
        }

    try:
        empresa_actual = st.session_state.empresa_usuario
        response = (
            supabase.table("configuracion_cliente")
            .select("*")
            .eq("empresa_nombre", empresa_actual)
            .execute()
        )
        if response.data and len(response.data) > 0:
            return response.data[0]
    except Exception:
        pass

    return {
        "empresa_nombre": st.session_state.get("empresa_usuario", "Mi Empresa Comex"),
        "ver_modulo_financiero": True,
        "ver_modulo_logistico": True,
        "ver_simulador": True,
        "alerta_margen_limite": 15.0,
    }


config_cliente = obtener_configuracion_cliente()

if "df_comex" not in st.session_state and supabase is not None:
    try:
        response = supabase.table("datos_comex").select("*").execute()
        if response.data:
            st.session_state["df_comex"] = pd.DataFrame(response.data)
        else:
            st.session_state["df_comex"] = pd.DataFrame()
    except Exception:
        st.session_state["df_comex"] = pd.DataFrame()

st.title(f"📊 Comex BI — {config_cliente.get('empresa_nombre', 'Plataforma Enterprise')}")


# --- 4. BARRA LATERAL ORGANIZADA ---
st.sidebar.header("⚙️ Panel de Control")

# Opciones de navegación base
opciones_menu = ["📈 Dashboard y Análisis", "📂 Importar Nuevos Datos / Lotes", "🗑️ Auditoría y Gestión de Lotes"]

# Si el usuario es administrador, le agregamos el módulo de Gestión de Usuarios en el menú
if st.session_state.get("rol_usuario") == "admin":
    opciones_menu.append("👥 Gestión de Usuarios")

seccion_principal = st.sidebar.radio("Navegación", opciones_menu)

st.sidebar.divider()
st.sidebar.subheader("💱 Parámetros Económicos")
tipo_cambio = st.sidebar.number_input("Tipo de Cambio (ARS/USD)", value=1000.0, step=10.0)

st.sidebar.divider()
st.sidebar.subheader("👤 Perfil y Permisos")
st.sidebar.text(f"Rol: {st.session_state.get('rol_usuario', 'N/A').upper()}")
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state.user = None
    if "session_token" in st.query_params:
        del st.query_params["session_token"]
    if "df_comex" in st.session_state:
        del st.session_state["df_comex"]
    st.rerun()


# --- SECCIÓN: IMPORTAR NUEVOS DATOS (ACUMULATIVO POR LOTE) ---
if seccion_principal == "📂 Importar Nuevos Datos / Lotes":
    st.subheader("📂 Gestión e Importación de Lotes Excel")
    st.markdown("Subí nuevos archivos Excel para **acumular e incorporar más operaciones** a la base de datos sin perder el histórico anterior.")

    if st.session_state.get("rol_usuario") in ["admin", "operativo"]:
        archivo_subido = st.file_uploader("Seleccionar archivo Excel", type=["xlsx", "xls"])
        nombre_lote = st.text_input("Identificador del Lote (Ej: Carga_Marzo_2026)", value=f"Lote_{datetime.now().strftime('%Y%m%d_%H%M')}")
        
        if archivo_subido is not None:
            df_original = pd.read_excel(archivo_subido)
            st.write("Vista previa del archivo seleccionado:")
            st.dataframe(df_original.head(), use_container_width=True)

            columnas_excel = df_original.columns.tolist()

            st.markdown("### Mapeo de Columnas")
            c1, c2 = st.columns(2)
            
            idx_f = 0 if len(columnas_excel) > 0 else 0
            idx_p = 1 if len(columnas_excel) > 1 else 0
            idx_c = 4 if len(columnas_excel) > 4 else 0
            idx_v = 3 if len(columnas_excel) > 3 else 0
            idx_pr = 2 if len(columnas_excel) > 2 else 0
            idx_d = 5 if len(columnas_excel) > 5 else 0

            with c1:
                col_fecha = st.selectbox("Fecha:", columnas_excel, index=idx_f)
                col_producto = st.selectbox("Producto:", columnas_excel, index=idx_p)
                col_cantidad = st.selectbox("Cantidad:", columnas_excel, index=idx_c)
            with c2:
                col_valor = st.selectbox("Valor FOB:", columnas_excel, index=idx_v)
                col_proveedor = st.selectbox("Proveedor:", columnas_excel, index=idx_pr)
                col_destino = st.selectbox("Destino:", columnas_excel, index=idx_d)

            if st.button("🚀 Consolidar y Guardar Lote en la Nube", type="primary"):
                df_estandarizado = pd.DataFrame()
                df_estandarizado["fecha"] = pd.to_datetime(df_original[col_fecha], errors="coerce")
                df_estandarizado["producto"] = df_original[col_producto].astype(str)
                df_estandarizado["cantidad"] = pd.to_numeric(df_original[col_cantidad], errors="coerce").fillna(0)
                df_estandarizado["valor_fob"] = pd.to_numeric(df_original[col_valor], errors="coerce").fillna(0)
                df_estandarizado["proveedor"] = df_original[col_proveedor].astype(str)
                df_estandarizado["destino"] = df_original[col_destino].astype(str)
                df_estandarizado["lote_origen"] = nombre_lote

                if supabase is not None:
                    try:
                        registros = []
                        for _, row in df_estandarizado.iterrows():
                            registros.append({
                                "fecha": row["fecha"].strftime("%Y-%m-%d") if pd.notnull(row["fecha"]) else None,
                                "producto": row["producto"],
                                "cantidad": float(row["cantidad"]),
                                "valor_fob": float(row["valor_fob"]),
                                "destino": row["destino"],
                                "proveedor": row["proveedor"],
                                "lote_origen": row["lote_origen"]
                            })
                        supabase.table("datos_comex").insert(registros).execute()
                        st.success(f"¡Lote '{nombre_lote}' importado y acumulado exitosamente en Supabase!")
                        
                        response = supabase.table("datos_comex").select("*").execute()
                        if response.data:
                            st.session_state["df_comex"] = pd.DataFrame(response.data)
                    except Exception as e:
                        st.error(f"Error al guardar en base de datos: {e}")
    else:
        st.info("Modo visualización: No tenés permisos operativos para importar nuevos lotes.")


# --- SECCIÓN: GESTIÓN DE USUARIOS (MÓDULO EXCLUSIVO ADMIN) ---
elif seccion_principal == "👥 Gestión de Usuarios":
    st.subheader("👥 Alta y Administración de Usuarios")
    st.markdown("Creá cuentas de acceso de manera segura para los colaboradores de tu empresa y asignales sus roles correspondientes.")

    if st.session_state.get("rol_usuario") == "admin":
        # Formulario de Alta
        with st.form("form_crear_usuario"):
            st.markdown("### Registrar Nuevo Usuario")
            nuevo_email = st.text_input("Correo Electrónico del Colaborador")
            nuevo_password = st.text_input("Contraseña Temporal", type="password")
            
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                rol_asignado = st.selectbox("Rol en el Sistema", ["visor", "operativo", "admin"])
            with col_r2:
                empresa_asignada = st.text_input("Empresa", value=st.session_state.get("empresa_usuario", "COMEX_Sistema"))
            
            btn_crear_user = st.form_submit_button("✨ Crear Usuario en la Nube", type="primary")

        if btn_crear_user:
            if not nuevo_email or not nuevo_password:
                st.error("Por favor, completá el correo y la contraseña temporal.")
            else:
                try:
                    try:
                        supabase.auth.sign_up({
                            "email": nuevo_email,
                            "password": nuevo_password
                        })
                    except Exception:
                        pass
                    
                    verif_existente = supabase.table("user_profiles").select("email").eq("email", nuevo_email).execute()
                    datos_perfil = {
                        "email": nuevo_email,
                        "Rol": rol_asignado,
                        "empresa": empresa_asignada
                    }
                    
                    if verif_existente.data and len(verif_existente.data) > 0:
                        supabase.table("user_profiles").update(datos_perfil).eq("email", nuevo_email).execute()
                        st.success(f"¡El usuario **{nuevo_email}** fue actualizado con éxito!")
                    else:
                        supabase.table("user_profiles").insert(datos_perfil).execute()
                        st.success(f"¡El usuario **{nuevo_email}** fue registrado con éxito con el rol **{rol_asignado}**!")
                    
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar el usuario. Detalle: {e}")
        
        st.divider()
        st.markdown("### Listado y Gestión de Usuarios Actuales")
        
        try:
            res_usuarios = supabase.table("user_profiles").select("*").execute()
            if res_usuarios.data:
                df_users = pd.DataFrame(res_usuarios.data)
                st.dataframe(df_users, use_container_width=True)
                
                # --- SECCIÓN DE ELIMINACIÓN DE USUARIOS ---
                st.markdown("#### 🗑️ Eliminar Usuario")
                emails_disponibles = [u["email"] for u in res_usuarios.data if u["email"] != st.session_state.get("usuario_email")]
                
                if emails_disponibles:
                    with st.form("form_eliminar_usuario"):
                        email_a_borrar = st.selectbox("Seleccioná el correo del usuario a eliminar", emails_disponibles)
                        btn_eliminar = st.form_submit_button("❌ Eliminar Usuario Seleccionado", type="secondary")
                    
                    if btn_eliminar:
                        try:
                            # Borramos el perfil de la tabla user_profiles
                            supabase.table("user_profiles").delete().eq("email", email_a_borrar).execute()
                            st.success(f"¡El usuario **{email_a_borrar}** fue eliminado del sistema con éxito!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo eliminar el usuario: {e}")
                else:
                    st.info("No hay otros usuarios disponibles para eliminar (no podés borrar tu propia cuenta de administrador actual).")
            else:
                st.info("No se encontraron perfiles registrados.")
        except Exception as e:
            st.error(f"No se pudo cargar el listado de usuarios: {e}")
    else:
        st.warning("⚠️ No tenés permisos de Administrador para ver esta sección.")
              
            
# --- SECCIÓN: DASHBOARD Y ANALÍTICA ---
elif seccion_principal == "📈 Dashboard y Análisis":
    if "df_comex" in st.session_state and not st.session_state["df_comex"].empty:
        df = st.session_state["df_comex"]
        df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")

        st.sidebar.divider()
        st.sidebar.subheader("📅 Filtrar por Período")
        min_f = df["fecha"].min().date() if pd.notnull(df["fecha"].min()) else datetime.today().date()
        max_f = df["fecha"].max().date() if pd.notnull(df["fecha"].max()) else datetime.today().date()

        rango_fechas = st.sidebar.date_input(
            "Rango de Fechas", value=(min_f, max_f), min_value=min_f, max_value=max_f
        )
        
        if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
            inicio, fin = rango_fechas
            df_filtrado = df[(df["fecha"].dt.date >= inicio) & (df["fecha"].dt.date <= fin)]
        else:
            df_filtrado = df

        ver_en_moneda_local = st.sidebar.checkbox("Mostrar valores en Moneda Local (ARS)")
        factor_mult = tipo_cambio if ver_en_moneda_local else 1.0
        moneda_simbolo = "$" if ver_en_moneda_local else "US$"

        nombres_solapas = []
        if config_cliente.get("ver_modulo_financiero", True):
            nombres_solapas.append("📊 Resumen Ejecutivo")
        if config_cliente.get("ver_modulo_logistico", True):
            nombres_solapas.append("💰 Proveedores y Alertas")
        if config_cliente.get("ver_simulador", True):
            nombres_solapas.append("🎛️ Simulador What-If")

        if nombres_solapas:
            solapas = st.tabs(nombres_solapas)
            indice_tab = 0

            if config_cliente.get("ver_modulo_financiero", True):
                with solapas[indice_tab]:
                    st.subheader("Indicadores Clave del Negocio")
                    col1, col2, col3 = st.columns(3)

                    total_fob = df_filtrado["valor_fob"].sum() * factor_mult
                    total_ops = len(df_filtrado)
                    unidades = df_filtrado["cantidad"].sum()

                    col1.metric("Gasto Total Acumulado", f"{moneda_simbolo} {total_fob:,.2f}")
                    col2.metric("Operaciones Totales", f"{total_ops:,}")
                    col3.metric("Unidades Movilizadas", f"{unidades:,.0f}")

                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                        df_filtrado.to_excel(writer, sheet_name="Reporte_Comex", index=False)
                    buffer.seek(0)

                    st.download_button(
                        label="📥 Descargar Reporte Filtrado en Excel",
                        data=buffer,
                        file_name=f"reporte_comex_{datetime.now().strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

                    st.markdown("---")
                    st.dataframe(df_filtrado, use_container_width=True)
                indice_tab += 1

            if config_cliente.get("ver_modulo_logistico", True):
                with solapas[indice_tab]:
                    st.subheader("Análisis y Alertas Automáticas de Proveedores")
                    limite_alerta = config_cliente.get("alerta_margen_limite", 15.0)
                    prov_gasto = df_filtrado.groupby("proveedor")["valor_fob"].sum().reset_index()

                    if not prov_gasto.empty:
                        gasto_medio = prov_gasto["valor_fob"].mean()
                        for _, row in prov_gasto.iterrows():
                            if row["valor_fob"] > gasto_medio * (1 + limite_alerta / 100):
                                st.warning(
                                    f"⚠️ **Alerta de Desvío:** El proveedor **{row['proveedor']}** "
                                    f"supera el umbral de gasto promedio configurado ({limite_alerta}%)."
                                )

                    st.bar_chart(prov_gasto.set_index("proveedor")["valor_fob"])
                indice_tab += 1

            if config_cliente.get("ver_simulador", True):
                with solapas[indice_tab]:
                    st.subheader("Simulador What-If de Costos")
                    porcentaje = st.slider("Variación estimada de costos (%)", -30, 50, 0)
                    total_sim = df_filtrado["valor_fob"].sum() * factor_mult * (1 + porcentaje / 100)
                    st.metric(
                        "Impacto Total Simulado",
                        f"{moneda_simbolo} {total_sim:,.2f}",
                        delta=f"{porcentaje}%",
                    )
                indice_tab += 1
    else:
        st.warning("⚠️ No hay datos cargados en el sistema. Andá a la sección **'📂 Importar Nuevos Datos / Lotes'** en la barra lateral para subir tu primer archivo Excel.")