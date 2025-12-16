import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import time
from datetime import date
import re
import sys
import os

# ==========================================
# 1. CONFIGURACIÓN Y CONEXIÓN
# ==========================================
st.set_page_config(page_title="Atlis Logistics | ERP", page_icon="🚛", layout="wide")

try:
    DATABASE_URL = st.secrets["db"]["url"]
except:
    st.error("No se encontró la URL de la base de datos en los secretos.")
    st.stop()

# --- ESTILOS: MODO OSCURO ---
st.markdown("""
<style>
    .stApp { background-color: #101922; color: #E2E8F0; }
    div[data-testid="stMetric"] { background-color: #1A232E; border: 1px solid #2D3748; padding: 15px; border-radius: 8px; }
    div[data-testid="stMetricLabel"] { color: #94A3B8; font-size: 13px; font-weight: 500; }
    div[data-testid="stMetricValue"] { color: #FFFFFF; font-size: 24px; font-weight: 600; }
    section[data-testid="stSidebar"] { background-color: #0d1319; border-right: 1px solid #2D3748; }
    div.stButton > button { border-radius: 6px; font-weight: 500; border: none; }
    div[data-testid="stDataFrame"] { background-color: #1A232E; border-radius: 8px; }
    .stTextInput > div > div > input, .stSelectbox > div > div > div, .stNumberInput > div > div > input { 
        background-color: #1A232E; color: white; border: 1px solid #2D3748; 
    }
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)

try:
    engine = get_engine()
except Exception as e:
    st.error(f"❌ Error fatal de conexión a Supabase: {e}")
    st.stop()

# ==========================================
# 2. SISTEMA DE LOGIN
# ==========================================

if 'usuario_activo' not in st.session_state:
    st.session_state.usuario_activo = None

def check_login(usuario, clave):
    try:
        with engine.connect() as conn:
            sql = text('SELECT * FROM "USUARIOS" WHERE username = :u AND password = :p')
            result = conn.execute(sql, {"u": usuario, "p": clave}).fetchone()
            return result
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

if st.session_state.usuario_activo is None:
    st.markdown("<h1 style='text-align: center;'>🔐 Acceso LogisticsHub</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            user_input = st.text_input("Usuario")
            pass_input = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Ingresar", type="primary", use_container_width=True):
                user_data = check_login(user_input, pass_input)
                if user_data:
                    st.session_state.usuario_activo = user_data[1]
                    st.toast("¡Bienvenido!", icon="👋")
                    time.sleep(0.5)
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")
    st.stop()

# ==========================================
# 3. MENÚ LATERAL
# ==========================================
with st.sidebar:
    st.title("LogisticsHub")
    st.caption(f"Usuario: {st.session_state.usuario_activo}")
    st.markdown("---")
    if st.button("Cerrar Sesión"):
        st.session_state.usuario_activo = None
        st.rerun()
    st.markdown("---")
    menu = st.radio("Módulos", 
        ["Dashboard", "Gestión de Flota", "Conductores", "Clientes", "Rutas", "Tarifarios", "Registrar Viaje", "Carga Masiva (Excel)"], 
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.info("Sistema Operativo v8.0 (Fix Numpy & Names)")

# ==========================================
# 4. FUNCIONES HELPER GLOBALES
# ==========================================

@st.cache_data(ttl=60)
def load_maestros():
    try:
        df_cli = pd.read_sql('SELECT id_cliente, nombre FROM "CLIENTE"', engine)
        df_rut = pd.read_sql('SELECT id_ruta, origen, destino, km_estimados, tarifa_sugerida FROM "RUTAS"', engine)
        df_con = pd.read_sql('SELECT id_conductor, nombre FROM "CONDUCTORES"', engine)
        df_cam = pd.read_sql('SELECT id_camion, patente, marca FROM "CAMIONES"', engine)
        df_tar = pd.read_sql('SELECT id_cliente, id_ruta, monto_pactado FROM "TARIFAS"', engine)
        return df_cli, df_rut, df_con, df_cam, df_tar
    except Exception as e:
        st.error(f"Error cargando maestros: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def get_or_create_ruta(origen_abbr, destino_abbr):
    """Busca ruta por nombre. Si no existe, la crea con 0 KM."""
    if not origen_abbr or not destino_abbr or str(origen_abbr) == 'nan' or str(destino_abbr) == 'nan':
        return None, False

    origen_abbr = str(origen_abbr).strip().upper()
    destino_abbr = str(destino_abbr).strip().upper()
    
    # Recargar maestros
    df_rutas = pd.read_sql('SELECT id_ruta, origen, destino FROM "RUTAS"', engine)
    
    match = df_rutas[(df_rutas['origen'].str.upper() == origen_abbr) & (df_rutas['destino'].str.upper() == destino_abbr)]
    
    if not match.empty:
        # IMPORTANTE: Convertir a int nativo de Python (no numpy)
        return int(match.iloc[0]['id_ruta']), False
    
    try:
        with engine.begin() as conn:
            sql_insert = text("""
                INSERT INTO "RUTAS" (origen, destino, km_estimados, tarifa_sugerida)
                VALUES (:o, :d, :k, 0)
                RETURNING id_ruta
            """)
            result = conn.execute(sql_insert, {"o": origen_abbr, "d": destino_abbr, "k": 0}).fetchone()
            st.toast(f"Ruta nueva creada: {origen_abbr} -> {destino_abbr}", icon="🆕")
            return int(result[0]), True
    except Exception as e:
        st.error(f"Error al crear ruta automática: {e}")
        return None, True

def get_precio_automatico(id_cliente, id_ruta, df_rutas, df_tarifas):
    """Lógica inteligente de precios: Tarifa Especial > Tarifa Ruta > 0"""
    if id_ruta is None: return 0.0
    
    # 1. Buscar Tarifa Especial
    tarifa_match = df_tarifas[(df_tarifas['id_cliente'] == id_cliente) & (df_tarifas['id_ruta'] == id_ruta)]
    if not tarifa_match.empty:
        return float(tarifa_match.iloc[0]['monto_pactado'])
    
    # 2. Buscar Tarifa Genérica de la Ruta
    ruta_match = df_rutas[df_rutas['id_ruta'] == id_ruta]
    if not ruta_match.empty:
        return float(ruta_match.iloc[0]['tarifa_sugerida'])
    
    return 0.0

# ==========================================
# 5. MÓDULOS DE LA APP
# ==========================================

# --- A. DASHBOARD ---
if menu == "Dashboard":
    st.header("📊 Dashboard Gerencial")
    st.markdown("---")
    try:
        with engine.connect() as conn:
            sql_finance = 'SELECT COUNT(id_viaje), COALESCE(SUM(monto_neto), 0) FROM "VIAJES"'
            finance_data = conn.execute(text(sql_finance)).fetchone()
            total_viajes, ingreso_total = finance_data[0], finance_data[1]
            n_cam = pd.read_sql('SELECT COUNT(*) FROM "CAMIONES"', conn).iloc[0,0]
            n_cli = pd.read_sql('SELECT COUNT(*) FROM "CLIENTE"', conn).iloc[0,0]
    except:
        total_viajes, ingreso_total, n_cam, n_cli = 0, 0, 0, 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Venta Real Acumulada", f"${ingreso_total:,.0f}".replace(",", "."))
    c2.metric("Viajes Totales", total_viajes)
    c3.metric("Flota", n_cam)
    c4.metric("Clientes", n_cli)

    st.markdown("### 📋 Últimos Movimientos")
    try:
        df_last = pd.read_sql("""
            SELECT v.id_viaje, v.fecha, cl.nombre as cliente, r.destino, 
                   CONCAT('$', v.monto_neto) as valor_cobrado, v.estado 
            FROM "VIAJES" v
            LEFT JOIN "RUTAS" r ON v.id_ruta = r.id_ruta
            LEFT JOIN "CLIENTE" cl ON v.id_cliente = cl.id_cliente
            ORDER BY v.fecha DESC LIMIT 10
        """, engine)
        st.dataframe(df_last, use_container_width=True, hide_index=True)
    except: pass

# --- B. GESTIÓN DE FLOTA ---
elif menu == "Gestión de Flota":
    st.header("🚚 Inventario de Flota")
    tab_new, tab_edit = st.tabs(["➕ Nuevo Vehículo", "✏️ Modificar / Eliminar"])
    
    with tab_new:
        with st.form("new_truck", clear_on_submit=True):
            c1, c2 = st.columns(2)
            pat = c1.text_input("Patente *")
            marca = c1.selectbox("Marca", ["Scania", "Volvo", "Mercedes-Benz", "Freightliner", "International", "Volkswagen", "JAC", "Otro"])
            mod = c2.text_input("Modelo")
            ani = c2.number_input("Año", 1990, 2030, 2024)
            rend = st.number_input("Rendimiento (Km/L)", 1.0, 8.0, 2.5)
            
            if st.form_submit_button("Guardar Vehículo"):
                if pat:
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("INSERT INTO \"CAMIONES\" (patente, marca, modelo, \"año\", rendimiento_esperado) VALUES (:p, :m, :mo, :a, :r)"),
                                         {"p": pat, "m": marca, "mo": mod, "a": ani, "r": rend})
                        st.success("Guardado")
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
                if st.button("Eliminar Vehículo"):
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM \"CAMIONES\" WHERE id_camion=:id"), {"id": id_sel})
                        st.success("Eliminado")
                        time.sleep(1)
                        st.rerun()
                    except: st.error("No se puede eliminar (tiene viajes).")
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
                st.success("Guardado")
                time.sleep(1)
                st.rerun()

    with tab_edit:
        try:
            df = pd.read_sql('SELECT * FROM "CONDUCTORES" ORDER BY id_conductor DESC', engine)
            if not df.empty:
                map_con = {f"{r['nombre']} ({r['rut']})": r['id_conductor'] for i, r in df.iterrows()}
                sel = st.selectbox("Editar Conductor", list(map_con.keys()))
                id_sel = map_con[sel]
                row = df[df['id_conductor'] == id_sel].iloc[0]
                
                n_nom = st.text_input("Nombre", row['nombre'])
                n_act = st.checkbox("Activo", row['activo'])
                
                if st.button("💾 Guardar"):
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE \"CONDUCTORES\" SET nombre=:n, activo=:a WHERE id_conductor=:id"),
                                     {"n": n_nom, "a": n_act, "id": id_sel})
                    st.toast("Actualizado")
                    time.sleep(1)
                    st.rerun()
                if st.button("🗑️ Eliminar"):
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM \"CONDUCTORES\" WHERE id_conductor=:id"), {"id": id_sel})
                        st.success("Eliminado")
                        time.sleep(1)
                        st.rerun()
                    except: st.error("No se puede eliminar.")
        except: pass
    st.dataframe(pd.read_sql('SELECT * FROM "CONDUCTORES"', engine), use_container_width=True)

# --- D. CLIENTES ---
elif menu == "Clientes":
    st.header("🏢 Clientes")
    tab_new, tab_edit = st.tabs(["➕ Registrar", "✏️ Modificar / Eliminar"])

    with tab_new:
        with st.form("cli_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            nom = col1.text_input("Nombre Empresa")
            rut = col2.text_input("RUT Empresa")
            con = st.text_input("Contacto")
            if st.form_submit_button("Guardar Cliente"):
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO \"CLIENTE\" (nombre, rut_empresa, contacto) VALUES (:n, :r, :c)"),
                                 {"n": nom, "r": rut, "c": con})
                st.success("Guardado")
                time.sleep(1)
                st.rerun()
    
    with tab_edit:
        try:
            df_cli = pd.read_sql('SELECT * FROM "CLIENTE" ORDER BY id_cliente DESC', engine)
            if not df_cli.empty:
                map_cli = {f"{r['nombre']}": r['id_cliente'] for i, r in df_cli.iterrows()}
                sel_cli = st.selectbox("Editar Cliente", list(map_cli.keys()))
                id_sel = map_cli[sel_cli]
                
                if st.button("🗑️ Eliminar Cliente"):
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM \"CLIENTE\" WHERE id_cliente=:id"), {"id": id_sel})
                        st.success("Eliminado")
                        time.sleep(1)
                        st.rerun()
                    except: st.error("No se puede eliminar (tiene datos asociados).")
        except: pass
    st.dataframe(pd.read_sql('SELECT * FROM "CLIENTE"', engine), use_container_width=True)

# --- E. RUTAS ---
elif menu == "Rutas":
    st.header("🛣️ Rutas Físicas")
    tab_new, tab_edit = st.tabs(["➕ Crear", "✏️ Editar"])
    
    with tab_new:
        with st.form("ruta_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            ori = c1.text_input("Origen", "STI")
            des = c2.text_input("Destino")
            km = c1.number_input("Kms", 0, 5000)
            tar = c2.number_input("Tarifa Base ($)", 0, 5000000)
            if st.form_submit_button("Crear Ruta"):
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO \"RUTAS\" (origen, destino, km_estimados, tarifa_sugerida) VALUES (:o, :d, :k, :t)"),
                                 {"o": ori, "d": des, "k": km, "t": tar})
                st.success("Ruta creada")
                time.sleep(1)
                st.rerun()
    
    with tab_edit:
        df_rutas = pd.read_sql('SELECT * FROM "RUTAS"', engine)
        if not df_rutas.empty:
            map_rut = {f"{r['origen']} -> {r['destino']}": r['id_ruta'] for i, r in df_rutas.iterrows()}
            sel = st.selectbox("Editar Ruta", list(map_rut.keys()))
            id_sel = map_rut[sel]
            row = df_rutas[df_rutas['id_ruta'] == id_sel].iloc[0]
            
            c1, c2 = st.columns(2)
            n_ori = c1.text_input("Origen", row['origen'])
            n_des = c2.text_input("Destino", row['destino'])
            n_km = c1.number_input("Kms", value=int(row['km_estimados']))
            n_tar = c2.number_input("Tarifa Base", value=int(row['tarifa_sugerida']))
            
            if st.button("Actualizar"):
                with engine.begin() as conn:
                    conn.execute(text("UPDATE \"RUTAS\" SET origen=:o, destino=:d, km_estimados=:k, tarifa_sugerida=:t WHERE id_ruta=:id"),
                                 {"o": n_ori, "d": n_des, "k": n_km, "t": n_tar, "id": id_sel})
                st.toast("Actualizado")
                time.sleep(1)
                st.rerun()
            if st.button("Eliminar Ruta"):
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM \"RUTAS\" WHERE id_ruta=:id"), {"id": id_sel})
                st.rerun()
        st.dataframe(df_rutas, use_container_width=True)

# --- F. TARIFARIOS ---
elif menu == "Tarifarios":
    st.header("💰 Tarifas por Cliente")
    df_cli, df_rut, _, _, _ = load_maestros()
    
    with st.form("tarifas_form"):
        c1, c2 = st.columns(2)
        idx_cli = c1.selectbox("Cliente", df_cli.index, format_func=lambda x: df_cli.iloc[x]['nombre'])
        idx_rut = c2.selectbox("Ruta", df_rut.index, format_func=lambda x: f"{df_rut.iloc[x]['origen']} -> {df_rut.iloc[x]['destino']}")
        precio = st.number_input("Precio Pactado ($)", 0, step=1000)
        
        if st.form_submit_button("Guardar Tarifa"):
            try:
                cli_id = int(df_cli.iloc[idx_cli]['id_cliente'])
                rut_id = int(df_rut.iloc[idx_rut]['id_ruta'])
                with engine.begin() as conn:
                    sql = text("""
                        INSERT INTO "TARIFAS" (id_cliente, id_ruta, monto_pactado) VALUES (:c, :r, :m)
                        ON CONFLICT (id_cliente, id_ruta) DO UPDATE SET monto_pactado = EXCLUDED.monto_pactado
                    """)
                    conn.execute(sql, {"c": cli_id, "r": rut_id, "m": precio})
                st.success("Tarifa guardada")
            except Exception as e: st.error(f"Error: {e}")
            
    st.dataframe(pd.read_sql('SELECT * FROM "TARIFAS"', engine), use_container_width=True)

# --- G. REGISTRAR VIAJE ---
elif menu == "Registrar Viaje":
    st.header("🚀 Nuevo Viaje Manual")
    df_cli, df_rut, df_con, df_cam, df_tar = load_maestros()
    
    if df_cli.empty or df_rut.empty:
        st.warning("Faltan datos maestros.")
    else:
        col1, col2 = st.columns(2)
        
        if 'sel_cli_idx' not in st.session_state: st.session_state.sel_cli_idx = 0
        if 'sel_rut_idx' not in st.session_state: st.session_state.sel_rut_idx = 0

        def update_ui(): pass

        idx_cli = col1.selectbox("Cliente", df_cli.index, format_func=lambda x: df_cli.iloc[x]['nombre'], key='sel_cli_idx', on_change=update_ui)
        idx_rut = col2.selectbox("Ruta", df_rut.index, format_func=lambda x: f"{df_rut.iloc[x]['destino']}", key='sel_rut_idx', on_change=update_ui)

        cli_id = int(df_cli.iloc[idx_cli]['id_cliente'])
        rut_id = int(df_rut.iloc[idx_rut]['id_ruta'])
        
        # Calcular precio automático
        precio_sug = get_precio_automatico(cli_id, rut_id, df_rut, df_tar)
        
        st.markdown("---")
        c_f1, c_f2, c_f3 = st.columns(3)
        fecha = c_f1.date_input("Fecha", date.today())
        monto_final = c_f3.number_input("Valor ($)", value=precio_sug, step=1000.0)
        
        if st.button("Confirmar Viaje", type="primary"):
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO \"VIAJES\" (fecha, id_cliente, id_ruta, monto_neto, estado) VALUES (:f, :c, :r, :m, 'Finalizado')"),
                             {"f": fecha, "c": cli_id, "r": rut_id, "m": monto_final})
            st.success("Viaje registrado")
            time.sleep(1)
            st.rerun()

# --- H. CARGA MASIVA (EXCEL) - FULL FIX ---
elif menu == "Carga Masiva (Excel)":
    st.header("📥 Carga Masiva de Guías (Excel)")
    df_cli, df_rut, _, _, df_tar = load_maestros()
    
    col_conf1, col_conf2 = st.columns(2)
    formato_sel = col_conf1.selectbox("Formato de Archivo", ["Formato TOBAR", "Formato COSIO"])
    
    if not df_cli.empty:
        idx_cliente_destino = col_conf2.selectbox("Asignar a Cliente (BD):", df_cli.index, format_func=lambda x: df_cli.iloc[x]['nombre'])
        id_cliente_bd = int(df_cli.iloc[idx_cliente_destino]['id_cliente'])
        nombre_cliente_bd = df_cli.iloc[idx_cliente_destino]['nombre']
    else:
        st.error("No hay clientes.")
        st.stop()

    uploaded_file = st.file_uploader("Subir Excel", type=["xlsx", "xlsm"])

    if uploaded_file and id_cliente_bd:
        try:
            viajes_a_cargar = []
            
            # --- 1. LECTURA Y LIMPIEZA DEL EXCEL ---
            if formato_sel == "Formato TOBAR":
                # Header en fila 24 (index 23). Leemos todo pero luego seleccionamos por nombre
                df_excel = pd.read_excel(uploaded_file, header=23)
                
                # LIMPIEZA DE COLUMNAS VACÍAS ("Unnamed")
                df_excel = df_excel.loc[:, ~df_excel.columns.str.contains('^Unnamed')]
                df_excel = df_excel.dropna(subset=['FECHA']).copy()
                
                # Iterar usando NOMBRES DE COLUMNA (Más seguro)
                for index, row in df_excel.iterrows():
                    # Tobar: "DESDE" y "HASTA" son columnas explicítas
                    origen = str(row['DESDE']).strip()
                    destino = str(row['HASTA']).strip()
                    
                    id_ruta, created = get_or_create_ruta(origen, destino)
                    precio = get_precio_automatico(id_cliente_bd, id_ruta, df_rut, df_tar) 
                    
                    # Construir observación
                    obs = f"Contenedor: {row['SIGLA CONTENEDOR']} {row['NUMERO CONTENEDOR']}"

                    viajes_a_cargar.append({
                        "fecha": row['FECHA'],
                        "id_cliente": id_cliente_bd,
                        "cliente_nombre": nombre_cliente_bd,
                        "id_ruta": id_ruta,
                        "ruta_nombre": f"{origen} -> {destino}",
                        "observaciones": obs,
                        "monto": precio
                    })

            elif formato_sel == "Formato COSIO":
                df_excel = pd.read_excel(uploaded_file, header=9)
                df_excel = df_excel.loc[:, ~df_excel.columns.str.contains('^Unnamed')]
                df_excel = df_excel.dropna(subset=['FECHA']).copy()
                
                for index, row in df_excel.iterrows():
                    origen = str(row['DESDE']).strip()
                    destino = str(row['HASTA']).strip()
                    
                    id_ruta, created = get_or_create_ruta(origen, destino)
                    
                    # Intentar leer monto del excel, si falla, calcular
                    try:
                        monto_str = str(row['MONTO']).replace('$','').replace('.','').replace(',','')
                        monto_excel = float(monto_str)
                    except:
                        monto_excel = get_precio_automatico(id_cliente_bd, id_ruta, df_rut, df_tar)

                    viajes_a_cargar.append({
                        "fecha": row['FECHA'],
                        "id_cliente": id_cliente_bd,
                        "cliente_nombre": nombre_cliente_bd,
                        "id_ruta": id_ruta,
                        "ruta_nombre": f"{origen} -> {destino}",
                        "observaciones": f"Contenedor: {row['CONTENEDOR']}",
                        "monto": monto_excel
                    })

            # --- PREVISUALIZACIÓN ---
            if viajes_a_cargar:
                st.markdown("### 🕵️‍♂️ Vista Previa (Datos a Insertar)")
                # Mostrar nombres bonitos en la tabla
                df_show = pd.DataFrame(viajes_a_cargar)
                st.dataframe(df_show[['fecha', 'cliente_nombre', 'ruta_nombre', 'monto', 'observaciones']], use_container_width=True)

                if st.button("✅ Confirmar e Importar", type="primary"):
                    count = 0
                    with engine.begin() as conn:
                        for v in viajes_a_cargar:
                            # --- CRÍTICO: CONVERSIÓN DE TIPOS PARA EVITAR ERROR NUMPY ---
                            # Convertimos todo explícitamente a tipos nativos de Python
                            try:
                                val_fecha = v['fecha']
                                val_cli = int(v['id_cliente'])  # int nativo
                                val_rut = int(v['id_ruta']) if v['id_ruta'] is not None else None # int nativo
                                val_mon = float(v['monto'])     # float nativo
                                val_obs = str(v['observaciones']) # string nativo
                                
                                sql = text("""
                                    INSERT INTO "VIAJES" (fecha, id_cliente, id_ruta, estado, monto_neto, observaciones)
                                    VALUES (:f, :c, :r, 'Finalizado', :m, :o)
                                """)
                                conn.execute(sql, {"f": val_fecha, "c": val_cli, "r": val_rut, "m": val_mon, "o": val_obs})
                                count += 1
                            except Exception as row_error:
                                st.error(f"Error en fila {count+1}: {row_error}")

                    st.success(f"¡Éxito! Se importaron {count} viajes correctamente.")
                    time.sleep(2)
                    st.rerun()
            else:
                st.info("No se encontraron filas válidas en el Excel.")

        except Exception as e:
            st.error(f"Error procesando el archivo: {e}")