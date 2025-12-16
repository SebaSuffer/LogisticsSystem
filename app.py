import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import time
from datetime import date

# ==========================================
# 1. CONFIGURACIÓN Y CONEXIÓN
# ==========================================
st.set_page_config(page_title="Atlis Logistics", page_icon="🚛", layout="wide")

try:
    DATABASE_URL = st.secrets["db"]["url"]
except:
    st.error("No se encontró la URL de la base de datos en los secretos.")
    st.stop()

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
        st.error(f"Error de conexión al validar usuario: {e}")
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
        ["Dashboard", "Gestión de Flota", "Conductores", "Clientes", "Rutas", "Tarifarios", "Registrar Viaje"], 
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.info("Sistema Operativo v6.3 (Tarifas)")

# ==========================================
# 4. LÓGICA DEL SISTEMA
# ==========================================

# --- A. DASHBOARD ---
if menu == "Dashboard":
    st.header("📊 Dashboard Gerencial")
    st.markdown("---")
    try:
        with engine.connect() as conn:
            # Ahora calculamos ingresos REALES basados en lo que se registró en el viaje
            sql_finance = 'SELECT COUNT(id_viaje), COALESCE(SUM(monto_neto), 0) FROM "VIAJES"'
            finance_data = conn.execute(text(sql_finance)).fetchone()
            total_viajes, ingreso_total = finance_data[0], finance_data[1]
            n_cam = pd.read_sql('SELECT COUNT(*) FROM "CAMIONES"', conn).iloc[0,0]
            n_cli = pd.read_sql('SELECT COUNT(*) FROM "CLIENTE"', conn).iloc[0,0]
    except Exception as e:
        st.error(f"Error calculando KPIs: {e}")
        total_viajes, ingreso_total, n_cam, n_cli = 0, 0, 0, 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Venta Real Acumulada", f"${ingreso_total:,.0f}".replace(",", "."))
    c2.metric("Viajes Totales", total_viajes)
    c3.metric("Flota", n_cam)
    c4.metric("Clientes", n_cli)

    st.markdown("### 📈 Análisis Operativo")
    col_g1, col_g2 = st.columns(2)
    try:
        df_cli_chart = pd.read_sql("""
            SELECT cl.nombre, COUNT(v.id_viaje) as viajes
            FROM "VIAJES" v JOIN "CLIENTE" cl ON v.id_cliente = cl.id_cliente
            GROUP BY cl.nombre ORDER BY viajes DESC LIMIT 5
        """, engine)
        with col_g1:
            st.subheader("Top Clientes")
            if not df_cli_chart.empty: st.bar_chart(df_cli_chart.set_index("nombre"), color="#137fec")
        
        df_est_chart = pd.read_sql('SELECT estado, COUNT(*) as cantidad FROM "VIAJES" GROUP BY estado', engine)
        with col_g2:
            st.subheader("Estado Viajes")
            if not df_est_chart.empty: st.bar_chart(df_est_chart.set_index("estado"), color="#2ecc71")
    except: pass

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
                        st.success("Guardado correctamente")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")

    with tab_edit:
        df_cam = pd.read_sql('SELECT * FROM "CAMIONES" ORDER BY id_camion DESC', engine)
        if not df_cam.empty:
            map_cam = {f"{r['patente']} - {r['marca']}": r['id_camion'] for i, r in df_cam.iterrows()}
            sel_cam = st.selectbox("Seleccionar Vehículo", list(map_cam.keys()))
            id_sel = map_cam[sel_cam]
            if st.button("Eliminar Vehículo", type="primary"):
                try:
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM \"CAMIONES\" WHERE id_camion=:id"), {"id": id_sel})
                    st.success("Eliminado")
                    time.sleep(1)
                    st.rerun()
                except: st.error("No se puede eliminar (tiene viajes asociados).")
        st.dataframe(df_cam, use_container_width=True)

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
                    conn.execute(text("INSERT INTO \"CONDUCTORES\" (nombre, rut, licencia, activo) VALUES (:n, :r, :l, true)"), {"n": nom, "r": rut, "l": lic})
                st.success("Guardado")
                time.sleep(1)
                st.rerun()
    with tab_edit:
        df = pd.read_sql('SELECT * FROM "CONDUCTORES"', engine)
        st.dataframe(df, use_container_width=True)

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
                conn.execute(text("INSERT INTO \"CLIENTE\" (nombre, rut_empresa, contacto) VALUES (:n, :r, :c)"), {"n": nom, "r": rut, "c": con})
            st.success("Cliente guardado")
            time.sleep(1)
            st.rerun()
    st.dataframe(pd.read_sql('SELECT * FROM "CLIENTE"', engine), use_container_width=True)

# --- E. RUTAS ---
elif menu == "Rutas":
    st.header("🛣️ Rutas Físicas")
    st.info("Aquí defines los tramos físicos. Los precios específicos por cliente se configuran en 'Tarifarios'.")
    
    with st.form("ruta_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        ori = c1.text_input("Origen", "Santiago")
        des = c2.text_input("Destino")
        km = c1.number_input("Kms", 0, 5000)
        tar_ref = c2.number_input("Tarifa Referencial (Mercado)", 0, 5000000)
        
        if st.form_submit_button("Crear Ruta"):
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO \"RUTAS\" (origen, destino, km_estimados, tarifa_sugerida) VALUES (:o, :d, :k, :t)"),
                             {"o": ori, "d": des, "k": km, "t": tar_ref})
            st.success("Ruta creada")
            time.sleep(1)
            st.rerun()
    st.dataframe(pd.read_sql('SELECT * FROM "RUTAS"', engine), use_container_width=True)

# --- F. TARIFARIOS (NUEVO MÓDULO) ---
elif menu == "Tarifarios":
    st.header("💰 Gestión de Tarifas por Cliente")
    st.markdown("Asigna precios especiales a clientes para rutas específicas.")
    
    try:
        df_cli = pd.read_sql('SELECT id_cliente, nombre FROM "CLIENTE"', engine)
        df_rut = pd.read_sql('SELECT id_ruta, destino, tarifa_sugerida FROM "RUTAS"', engine)
    except: st.stop()

    with st.form("tarifas_form"):
        c1, c2 = st.columns(2)
        idx_cli = c1.selectbox("Cliente", df_cli.index, format_func=lambda x: df_cli.iloc[x]['nombre'])
        idx_rut = c2.selectbox("Ruta", df_rut.index, format_func=lambda x: f"{df_rut.iloc[x]['destino']} (Ref: ${df_rut.iloc[x]['tarifa_sugerida']})")
        
        precio = st.number_input("Precio Pactado ($)", min_value=0, step=1000)
        
        if st.form_submit_button("Guardar Tarifa Especial"):
            try:
                cli_id = int(df_cli.iloc[idx_cli]['id_cliente'])
                rut_id = int(df_rut.iloc[idx_rut]['id_ruta'])
                
                with engine.begin() as conn:
                    # Upsert: Si existe actualiza, si no inserta (Postgres syntax)
                    sql = text("""
                        INSERT INTO "TARIFAS" (id_cliente, id_ruta, monto_pactado)
                        VALUES (:c, :r, :m)
                        ON CONFLICT (id_cliente, id_ruta) 
                        DO UPDATE SET monto_pactado = EXCLUDED.monto_pactado
                    """)
                    conn.execute(sql, {"c": cli_id, "r": rut_id, "m": precio})
                st.success(f"Tarifa actualizada para {df_cli.iloc[idx_cli]['nombre']}")
            except Exception as e:
                st.error(f"Error (Revisa si creaste la tabla TARIFAS en Supabase): {e}")

    st.subheader("Tarifas Vigentes")
    try:
        sql_view = """
            SELECT t.id_tarifa, c.nombre as Cliente, r.destino as Ruta, CONCAT('$', t.monto_pactado) as Precio_Pactado
            FROM "TARIFAS" t
            JOIN "CLIENTE" c ON t.id_cliente = c.id_cliente
            JOIN "RUTAS" r ON t.id_ruta = r.id_ruta
        """
        st.dataframe(pd.read_sql(sql_view, engine), use_container_width=True)
    except: st.info("No hay tarifas especiales configuradas o falta crear la tabla.")


# --- G. REGISTRAR VIAJE (INTELIGENTE) ---
elif menu == "Registrar Viaje":
    st.header("🚀 Nueva Operación")
    
    try:
        df_cli = pd.read_sql('SELECT * FROM "CLIENTE"', engine)
        df_rut = pd.read_sql('SELECT * FROM "RUTAS"', engine)
        df_con = pd.read_sql('SELECT * FROM "CONDUCTORES" WHERE activo=true', engine)
        df_cam = pd.read_sql('SELECT * FROM "CAMIONES"', engine)
        
        if df_cli.empty or df_rut.empty:
            st.warning("Faltan datos maestros.")
        else:
            # 1. SELECCIÓN DINÁMICA
            col1, col2 = st.columns(2)
            
            # Usamos session_state para detectar cambios en los selectbox y recargar el precio
            if 'sel_cli_idx' not in st.session_state: st.session_state.sel_cli_idx = 0
            if 'sel_rut_idx' not in st.session_state: st.session_state.sel_rut_idx = 0

            def update_price():
                # Esta función dummy fuerza el re-render para calcular precio
                pass

            idx_cli = col1.selectbox("Cliente", df_cli.index, 
                                   format_func=lambda x: df_cli.iloc[x]['nombre'],
                                   key='sel_cli_idx', on_change=update_price)
            
            idx_rut = col2.selectbox("Ruta", df_rut.index, 
                                   format_func=lambda x: f"A {df_rut.iloc[x]['destino']} ({df_rut.iloc[x]['km_estimados']} km)",
                                   key='sel_rut_idx', on_change=update_price)

            # 2. LÓGICA DE PRECIO AUTOMÁTICO
            cli_id_sel = int(df_cli.iloc[idx_cli]['id_cliente'])
            rut_id_sel = int(df_rut.iloc[idx_rut]['id_ruta'])
            precio_sugerido = float(df_rut.iloc[idx_rut]['tarifa_sugerida']) # Precio base por defecto

            # Consultar si hay tarifa especial
            try:
                with engine.connect() as conn:
                    res = conn.execute(text('SELECT monto_pactado FROM "TARIFAS" WHERE id_cliente=:c AND id_ruta=:r'), 
                                     {"c": cli_id_sel, "r": rut_id_sel}).fetchone()
                    if res:
                        precio_sugerido = float(res[0])
                        st.toast(f"✅ Tarifa especial aplicada: ${precio_sugerido:,.0f}", icon="💰")
            except: pass

            # 3. RESTO DEL FORMULARIO
            col3, col4 = st.columns(2)
            idx_con = col3.selectbox("Conductor", df_con.index, format_func=lambda x: df_con.iloc[x]['nombre'])
            idx_cam = col4.selectbox("Camión", df_cam.index, format_func=lambda x: df_cam.iloc[x]['patente'])
            
            st.markdown("---")
            c_f1, c_f2, c_f3 = st.columns(3)
            fecha = c_f1.date_input("Fecha Salida", date.today())
            estado = c_f2.selectbox("Estado", ["Programado", "En Ruta", "Finalizado"])
            
            # Aquí el usuario ve el precio sugerido (base o especial) y puede cambiarlo si quiere
            monto_final = c_f3.number_input("Valor a Cobrar (Neto)", value=precio_sugerido, step=1000.0)

            if st.button("Confirmar Viaje", type="primary"):
                try:
                    with engine.begin() as conn:
                        sql = text("""
                            INSERT INTO "VIAJES" (fecha, id_cliente, id_camion, id_conductor, id_ruta, estado, monto_neto)
                            VALUES (:f, :cl, :ca, :co, :ru, :es, :mn)
                        """)
                        conn.execute(sql, {
                            "f": fecha, 
                            "cl": cli_id_sel, 
                            "ca": int(df_cam.iloc[idx_cam]['id_camion']), 
                            "co": int(df_con.iloc[idx_con]['id_conductor']), 
                            "ru": rut_id_sel, 
                            "es": estado,
                            "mn": monto_final
                        })
                    st.success("Operación Registrada Exitosamente")
                    time.sleep(1.5)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al registrar: {e}")
                    
    except Exception as e:
        st.error(f"Error cargando formulario: {e}")