import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import time
from datetime import date

# ==========================================
# 1. CONFIGURACIÓN Y CONEXIÓN
# ==========================================
st.set_page_config(page_title="Atlis Logistics", page_icon="🚛", layout="wide")

# CONEXIÓN SEGURA USANDO SECRETS
try:
    DATABASE_URL = st.secrets["db"]["url"]
except:
    st.error("No se encontró la URL de la base de datos en los secretos (.streamlit/secrets.toml).")
    st.stop()

# ESTILOS
st.markdown("""
<style>
    .stApp { background-color: #101922; color: #E2E8F0; }
    div[data-testid="stMetric"] { background-color: #1A232E; border: 1px solid #2D3748; padding: 15px; border-radius: 8px; }
    section[data-testid="stSidebar"] { background-color: #0d1319; border-right: 1px solid #2D3748; }
    div.stButton > button { border-radius: 6px; font-weight: 500; border: none; }
    div[data-testid="stDataFrame"] { background-color: #1A232E; border-radius: 8px; }
    .stTextInput > div > div > input, .stSelectbox > div > div > div, .stNumberInput > div > div > input { 
        background-color: #1A232E; color: white; border: 1px solid #2D3748; 
    }
</style>
""", unsafe_allow_html=True)

# Cache de conexión
@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)

try:
    engine = get_engine()
except Exception as e:
    st.error(f"❌ Error fatal de conexión a Supabase: {e}")
    st.stop()

# ==========================================
# 2. SISTEMA DE LOGIN (NUEVO)
# ==========================================

# Inicializar estado de sesión
if 'usuario_activo' not in st.session_state:
    st.session_state.usuario_activo = None

def check_login(usuario, clave):
    try:
        with engine.connect() as conn:
            # Consulta segura con parámetros
            sql = text('SELECT * FROM "USUARIOS" WHERE username = :u AND password = :p')
            result = conn.execute(sql, {"u": usuario, "p": clave}).fetchone()
            return result
    except Exception as e:
        st.error(f"Error de conexión al validar usuario: {e}")
        return None

# --- PANTALLA DE LOGIN ---
if st.session_state.usuario_activo is None:
    st.markdown("<h1 style='text-align: center;'>🔐 Acceso LogisticsHub</h1>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            user_input = st.text_input("Usuario")
            pass_input = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Ingresar", type="primary", use_container_width=True)
            
            if submitted:
                user_data = check_login(user_input, pass_input)
                if user_data:
                    st.session_state.usuario_activo = user_data[1] # Guardamos el username
                    st.toast("¡Bienvenido!", icon="👋")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")
    
    # DETIENE EL CÓDIGO AQUÍ SI NO ESTÁ LOGUEADO
    st.stop()

# ==========================================
# 3. MENÚ LATERAL (SOLO VISIBLE SI LOGUEADO)
# ==========================================
with st.sidebar:
    st.title("LogisticsHub")
    st.caption(f"Usuario: {st.session_state.usuario_activo}")
    st.markdown("---")
    
    # Botón de Cerrar Sesión
    if st.button("Cerrar Sesión"):
        st.session_state.usuario_activo = None
        st.rerun()
        
    st.markdown("---")
    menu = st.radio("Módulos", 
        ["Panel de Control", "Gestión de Flota", "Conductores", "Clientes", "Rutas", "Registrar Viaje"], 
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.info("Sistema Operativo v6.1")

# ==========================================
# 4. LÓGICA DEL SISTEMA (RESTO DEL CÓDIGO)
# ==========================================

# --- A. PANEL DE CONTROL ---
if menu == "Panel de Control":
    st.header("Panel de Control Operativo")
    st.markdown("---")

    try:
        with engine.connect() as conn:
            n_cam = pd.read_sql('SELECT COUNT(*) FROM "CAMIONES"', conn).iloc[0,0]
            n_via = pd.read_sql('SELECT COUNT(*) FROM "VIAJES"', conn).iloc[0,0]
            n_cli = pd.read_sql('SELECT COUNT(*) FROM "CLIENTE"', conn).iloc[0,0]
    except Exception as e:
        # Si falla (ej: tabla no existe), ponemos ceros
        n_cam, n_via, n_cli = 0, 0, 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Flota Total", n_cam)
    c2.metric("Viajes Totales", n_via)
    c3.metric("Clientes Activos", n_cli)

    st.markdown("### 📋 Bitácora de Viajes Recientes")
    
    try:
        sql = """
            SELECT v.id_viaje, v.fecha, cl.nombre as cliente, c.patente, co.nombre as conductor, r.destino, v.estado 
            FROM "VIAJES" v
            LEFT JOIN "CAMIONES" c ON v.id_camion = c.id_camion
            LEFT JOIN "CONDUCTORES" co ON v.id_conductor = co.id_conductor
            LEFT JOIN "RUTAS" r ON v.id_ruta = r.id_ruta
            LEFT JOIN "CLIENTE" cl ON v.id_cliente = cl.id_cliente
            ORDER BY v.fecha DESC
        """
        df_viajes = pd.read_sql(sql, engine)
        st.dataframe(df_viajes, use_container_width=True, hide_index=True)

        if not df_viajes.empty:
            with st.expander("🗑️ Borrar Viaje Erróneo"):
                opts = {f"#{row['id_viaje']} - {row['cliente']} ({row['fecha']})": row['id_viaje'] for i, row in df_viajes.iterrows()}
                sel_viaje = st.selectbox("Seleccione viaje", list(opts.keys()))
                
                if st.button("Confirmar Eliminación", type="primary"):
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM \"VIAJES\" WHERE id_viaje = :id"), {"id": opts[sel_viaje]})
                    st.success("Viaje eliminado.")
                    time.sleep(1)
                    st.rerun()

    except Exception as e:
        st.error(f"Error cargando tabla: {e}")

# --- B. GESTIÓN DE FLOTA ---
elif menu == "Gestión de Flota":
    st.header("🚚 Inventario de Flota")
    tab_new, tab_edit = st.tabs(["➕ Nuevo Vehículo", "✏️ Modificar / Eliminar"])
    
    with tab_new:
        with st.form("new_truck", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                pat = st.text_input("Patente *")
                marca = st.selectbox("Marca", ["Scania", "Volvo", "Mercedes-Benz", "Freightliner", "International", "Kenworth", "Volkswagen", "JAC", "Otro"])
            with c2:
                modelo = st.text_input("Modelo")
                anio = st.number_input("Año", 1990, 2030, 2024)
                rend = st.number_input("Rendimiento (Km/L)", 1.0, 8.0, 2.5)
            
            if st.form_submit_button("Guardar Vehículo"):
                if pat:
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("INSERT INTO \"CAMIONES\" (patente, marca, modelo, \"año\", rendimiento_esperado) VALUES (:p, :m, :mo, :a, :r)"),
                                         {"p": pat, "m": marca, "mo": modelo, "a": anio, "r": rend})
                        st.success("Guardado correctamente")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    with tab_edit:
        try:
            df_cam = pd.read_sql('SELECT * FROM "CAMIONES" ORDER BY id_camion DESC', engine)
            if not df_cam.empty:
                map_cam = {f"{r['patente']} - {r['marca']}": r['id_camion'] for i, r in df_cam.iterrows()}
                sel_cam = st.selectbox("Seleccionar Vehículo", list(map_cam.keys()))
                id_sel = map_cam[sel_cam]
                row = df_cam[df_cam['id_camion'] == id_sel].iloc[0]

                c1, c2 = st.columns(2)
                n_pat = c1.text_input("Patente", row['patente'])
                n_mar = c1.text_input("Marca", row['marca'])
                n_mod = c2.text_input("Modelo", row['modelo'])
                n_anio = c2.number_input("Año", 1990, 2030, int(row['año']))

                if st.button("Actualizar Datos"):
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE \"CAMIONES\" SET patente=:p, marca=:m, modelo=:mo, \"año\"=:a WHERE id_camion=:id"),
                                     {"p": n_pat, "m": n_mar, "mo": n_mod, "a": n_anio, "id": id_sel})
                    st.success("Actualizado")
                    time.sleep(1)
                    st.rerun()
                
                if st.button("Eliminar Vehículo", type="primary"):
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM \"CAMIONES\" WHERE id_camion=:id"), {"id": id_sel})
                        st.success("Eliminado")
                        time.sleep(1)
                        st.rerun()
                    except: st.error("No se puede eliminar (tiene viajes asociados).")
        except: pass

    st.dataframe(pd.read_sql('SELECT * FROM "CAMIONES"', engine), use_container_width=True)

# --- C. CONDUCTORES ---
elif menu == "Conductores":
    st.header("👨‍✈️ Base de Conductores")
    tab_new, tab_edit = st.tabs(["➕ Nuevo", "✏️ Editar"])

    with tab_new:
        with st.form("new_driver", clear_on_submit=True):
            nom = st.text_input("Nombre Completo")
            rut = st.text_input("RUT")
            lic = st.selectbox("Licencia", ["A5", "A4", "A2", "B"])
            
            if st.form_submit_button("Guardar"):
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO \"CONDUCTORES\" (nombre, rut, licencia, activo) VALUES (:n, :r, :l, true)"),
                                 {"n": nom, "r": rut, "l": lic})
                st.success("Conductor Agregado")
                time.sleep(1)
                st.rerun()

    with tab_edit:
        try:
            df = pd.read_sql('SELECT * FROM "CONDUCTORES"', engine)
            if not df.empty:
                sel = st.selectbox("Editar Conductor", df['nombre'].tolist())
                row = df[df['nombre'] == sel].iloc[0]
                
                n_nom = st.text_input("Nombre", row['nombre'])
                n_act = st.checkbox("Activo", row['activo'])
                
                if st.button("Guardar Cambios"):
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE \"CONDUCTORES\" SET nombre=:n, activo=:a WHERE id_conductor=:id"),
                                     {"n": n_nom, "a": n_act, "id": row['id_conductor']})
                    st.rerun()
        except: pass
    
    st.dataframe(pd.read_sql('SELECT * FROM "CONDUCTORES"', engine), use_container_width=True)

# --- D. CLIENTES ---
elif menu == "Clientes":
    st.header("🏢 Clientes")
    with st.form("cli_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        nom = col1.text_input("Nombre Empresa")
        rut = col2.text_input("RUT Empresa")
        con = st.text_input("Contacto")
        if st.form_submit_button("Guardar Cliente"):
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO \"CLIENTE\" (nombre, rut_empresa, contacto) VALUES (:n, :r, :c)"),
                             {"n": nom, "r": rut, "c": con})
            st.success("Cliente guardado")
            time.sleep(1)
            st.rerun()
    
    st.dataframe(pd.read_sql('SELECT * FROM "CLIENTE"', engine), use_container_width=True)

# --- E. RUTAS ---
elif menu == "Rutas":
    st.header("🛣️ Rutas")
    with st.form("ruta_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        ori = c1.text_input("Origen", "Santiago")
        des = c2.text_input("Destino")
        km = c1.number_input("Kms", 0, 5000)
        tar = c2.number_input("Tarifa ($)", 0, 5000000)
        
        if st.form_submit_button("Crear Ruta"):
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO \"RUTAS\" (origen, destino, km_estimados, tarifa_sugerida) VALUES (:o, :d, :k, :t)"),
                             {"o": ori, "d": des, "k": km, "t": tar})
            st.success("Ruta creada")
            time.sleep(1)
            st.rerun()
            
    st.dataframe(pd.read_sql('SELECT * FROM "RUTAS"', engine), use_container_width=True)

# --- F. REGISTRAR VIAJE ---
elif menu == "Registrar Viaje":
    st.header("🚀 Nuevo Viaje")
    
    # Cargar datos para selects
    try:
        df_cli = pd.read_sql('SELECT * FROM "CLIENTE"', engine)
        df_rut = pd.read_sql('SELECT * FROM "RUTAS"', engine)
        df_con = pd.read_sql('SELECT * FROM "CONDUCTORES" WHERE activo=true', engine)
        df_cam = pd.read_sql('SELECT * FROM "CAMIONES"', engine)
        
        if df_cli.empty or df_rut.empty or df_con.empty or df_cam.empty:
            st.warning("Faltan datos maestros (Clientes, Rutas, etc) para crear viajes.")
        else:
            with st.form("viaje_form"):
                col1, col2 = st.columns(2)
                cli_id = col1.selectbox("Cliente", df_cli['id_cliente'], format_func=lambda x: df_cli[df_cli['id_cliente']==x]['nombre'].values[0])
                rut_id = col2.selectbox("Ruta", df_rut['id_ruta'], format_func=lambda x: f"{df_rut[df_rut['id_ruta']==x]['destino'].values[0]}")
                
                con_id = col1.selectbox("Conductor", df_con['id_conductor'], format_func=lambda x: df_con[df_con['id_conductor']==x]['nombre'].values[0])
                cam_id = col2.selectbox("Camión", df_cam['id_camion'], format_func=lambda x: df_cam[df_cam['id_camion']==x]['patente'].values[0])
                
                fecha = st.date_input("Fecha Salida", date.today())
                estado = st.selectbox("Estado", ["Programado", "En Ruta", "Finalizado"])
                
                if st.form_submit_button("Registrar Operación"):
                    with engine.begin() as conn:
                        sql = text("""
                            INSERT INTO "VIAJES" (fecha, id_cliente, id_camion, id_conductor, id_ruta, estado, monto_neto)
                            VALUES (:f, :cl, :ca, :co, :ru, :es, 0)
                        """)
                        conn.execute(sql, {"f": fecha, "cl": cli_id, "ca": cam_id, "co": con_id, "ru": rut_id, "es": estado})
                    st.success("Viaje registrado correctamente")
                    time.sleep(1.5)
                    st.rerun()
                    
    except Exception as e:
        st.error(f"Error cargando formularios: {e}")