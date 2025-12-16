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
st.set_page_config(page_title="Atlis Logistics", page_icon="🚛", layout="wide")

# CONEXIÓN SEGURA USANDO SECRETS
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
        ["Dashboard", "Gestión de Flota", "Conductores", "Clientes", "Rutas", "Tarifarios", "Registrar Viaje", "Importador Masivo"], 
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.info("Sistema Operativo v6.8 (FINAL FIX)")

# ==========================================
# 4. FUNCIONES HELPER GLOBALES
# ==========================================

@st.cache_data(ttl=60)
def load_maestros():
    """Carga todos los datos maestros necesarios para los selectores."""
    try:
        df_cli = pd.read_sql('SELECT id_cliente, nombre FROM "CLIENTE"', engine)
        df_rut = pd.read_sql('SELECT id_ruta, origen, destino, km_estimados, tarifa_sugerida FROM "RUTAS"', engine)
        df_con = pd.read_sql('SELECT id_conductor, nombre, rut, licencia, activo FROM "CONDUCTORES"', engine) # FIX: Traer todos los campos
        df_cam = pd.read_sql('SELECT id_camion, patente, marca FROM "CAMIONES"', engine)
        return df_cli, df_rut, df_con, df_cam
    except Exception as e:
        st.error(f"Error cargando maestros: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def get_or_create_ruta(origen_abbr, destino_abbr):
    """Busca una ruta en la DB. Si no existe, la crea con 0 KM."""
    
    ruta_key = f"{origen_abbr.upper()}->{destino_abbr.upper()}"
    
    # 1. Buscar la ruta existente
    df_rutas = load_maestros()[1]
    match = df_rutas[(df_rutas['origen'] == origen_abbr) & (df_rutas['destino'] == destino_abbr)]
    
    if not match.empty:
        return match.iloc[0]['id_ruta'], False
    
    # 2. Si no existe, crearla
    try:
        with engine.begin() as conn:
            sql_insert = text("""
                INSERT INTO "RUTAS" (origen, destino, km_estimados, tarifa_sugerida)
                VALUES (:o, :d, :k, 0)
                RETURNING id_ruta
            """)
            result = conn.execute(sql_insert, {"o": origen_abbr, "d": destino_abbr, "k": 0}).fetchone()
            load_maestros.clear() 
            st.warning(f"Nueva ruta '{ruta_key}' creada con 0 KM. ¡Debes actualizar los KMs en el módulo Rutas!")
            return result[0], True
    except Exception as e:
        st.error(f"Error al crear ruta automática: {e}")
        return None, True

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
    except Exception as e:
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


# --- C. CONDUCTORES (FIXED) ---
elif menu == "Conductores":
    st.header("👨‍✈️ Base de Conductores")
    tab_new, tab_edit = st.tabs(["➕ Nuevo", "✏️ Editar"])

    with tab_new:
        with st.form("new_driver", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nom = c1.text_input("Nombre Completo")
            rut = c1.text_input("RUT")
            lic = c2.selectbox("Licencia", ["A5", "A4", "A2", "B"])
            
            if st.form_submit_button("Guardar"):
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO \"CONDUCTORES\" (nombre, rut, licencia, activo) VALUES (:n, :r, :l, true)"),
                                 {"n": nom, "r": rut, "l": lic})
                st.success("Conductor Agregado")
                time.sleep(1)
                st.rerun()

    with tab_edit:
        try:
            df = pd.read_sql('SELECT * FROM "CONDUCTORES" ORDER BY id_conductor DESC', engine)
            if not df.empty:
                # 1. Selector
                map_con = {f"{r['nombre']} ({r['rut']})": r['id_conductor'] for i, r in df.iterrows()}
                sel = st.selectbox("Editar Conductor", list(map_con.keys()))
                id_sel = map_con[sel]
                row = df[df['id_conductor'] == id_sel].iloc[0]
                
                # 2. Formulario Edición
                n_nom = st.text_input("Nombre", row['nombre'])
                n_rut = st.text_input("RUT", row['rut'])
                n_lic = st.selectbox("Licencia", ["A5", "A4", "A2", "B"], index=["A5", "A4", "A2", "B"].index(row['licencia']) if row['licencia'] in ["A5", "A4", "A2", "B"] else 0)
                n_act = st.checkbox("Activo", row['activo'])
                
                if st.button("💾 Guardar Cambios"):
                    with engine.begin() as conn:
                        sql_upd = text("UPDATE \"CONDUCTORES\" SET nombre=:n, rut=:r, licencia=:l, activo=:a WHERE id_conductor=:id")
                        conn.execute(sql_upd, {"n": n_nom, "r": n_rut, "l": n_lic, "a": n_act, "id": row['id_conductor']})
                    st.toast("Actualizado", icon="🔄")
                    time.sleep(1)
                    st.rerun()
                
                if st.button("🗑️ Eliminar", type="primary"):
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM \"CONDUCTORES\" WHERE id_conductor=:id"), {"id": id_sel})
                        st.success("Eliminado")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e: st.error("No se puede eliminar (tiene viajes asociados).")
        except: pass
        
    st.markdown("### Nómina de Conductores")
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


# --- E. RUTAS (ACTUALIZADO CON MODIFICAR/ELIMINAR) ---
elif menu == "Rutas":
    st.header("🛣️ Rutas Físicas")
    st.info("Aquí defines los tramos físicos. Los precios específicos por cliente se configuran en 'Tarifarios'.")
    
    tab_new, tab_edit = st.tabs(["➕ Crear Ruta", "✏️ Modificar / Eliminar"])
    df_rutas = load_maestros()[1]

    # --- CREAR RUTA ---
    with tab_new:
        with st.form("ruta_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            ori = c1.text_input("Origen (Abreviatura)", "STI")
            des = c2.text_input("Destino (Abreviatura)")
            km = c1.number_input("Kms", 0, 5000)
            tar_ref = c2.number_input("Tarifa Referencial (Mercado)", 0, 5000000)
            
            if st.form_submit_button("Crear Ruta"):
                try:
                    with engine.begin() as conn:
                        conn.execute(text("INSERT INTO \"RUTAS\" (origen, destino, km_estimados, tarifa_sugerida) VALUES (:o, :d, :k, :t)"),
                                     {"o": ori, "d": des, "k": km, "t": tar_ref})
                    load_maestros.clear() 
                    st.success("Ruta creada")
                    time.sleep(1)
                    st.rerun()
                except Exception as e: st.error(f"Error al guardar: {e}")
    
    # --- MODIFICAR / ELIMINAR RUTA ---
    with tab_edit:
        if df_rutas.empty:
            st.info("No hay rutas registradas para modificar.")
        else:
            # 1. Selector de Ruta
            map_rut = {f"{r['origen']} -> {r['destino']} ({r['km_estimados']} Km)": r['id_ruta'] for i, r in df_rutas.iterrows()}
            sel_rut_label = st.selectbox("Seleccione Ruta a Editar", list(map_rut.keys()))
            id_sel = map_rut[sel_rut_label]
            
            # 2. Obtener datos de la ruta seleccionada
            row = df_rutas[df_rutas['id_ruta'] == id_sel].iloc[0]
            
            st.markdown("#### Editar Datos Físicos y Referenciales")
            col_e1, col_e2 = st.columns(2)
            
            new_ori = col_e1.text_input("Origen", value=row['origen'])
            new_des = col_e2.text_input("Destino", value=row['destino'])
            new_km = col_e1.number_input("Kms Reales", value=int(row['km_estimados']), min_value=0)
            new_tar = col_e2.number_input("Tarifa Referencial ($)", value=int(row['tarifa_sugerida']), min_value=0)

            # 3. Botones de Acción
            col_btn1, col_btn2 = st.columns([1, 4])
            if col_btn1.button("💾 Actualizar Ruta", type="primary"):
                try:
                    with engine.begin() as conn:
                        sql_upd = text("""
                            UPDATE "RUTAS" SET origen=:o, destino=:d, km_estimados=:k, tarifa_sugerida=:t 
                            WHERE id_ruta=:id
                        """)
                        conn.execute(sql_upd, {"o": new_ori, "d": new_des, "k": new_km, "t": new_tar, "id": id_sel})
                    load_maestros.clear() 
                    st.toast("Ruta Actualizada", icon="🔄")
                    time.sleep(1)
                    st.rerun()
                except Exception as e: st.error(f"Error al actualizar: {e}")
            
            st.markdown("---")
            if st.button("🗑️ Eliminar Ruta", type="primary"):
                try:
                    with engine.begin() as conn:
                        conn.execute(text("DELETE FROM \"RUTAS\" WHERE id_ruta = :id"), {"id": id_sel})
                    load_maestros.clear()
                    st.success("Ruta eliminada.")
                    time.sleep(1)
                    st.rerun()
                except Exception as e: st.error("No se puede eliminar: Rutas tiene viajes o tarifas asociadas. Borre esas dependencias primero.")
    
    st.markdown("### Listado Completo de Rutas")
    st.dataframe(df_rutas, use_container_width=True)


# --- F. TARIFARIOS ---
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


# --- G. REGISTRAR VIAJE ---
elif menu == "Registrar Viaje":
    st.header("🚀 Nueva Operación Manual")
    
    df_cli, df_rut, df_con, df_cam = load_maestros()

    if df_cli.empty or df_rut.empty:
        st.warning("Faltan datos maestros.")
    else:
        # 1. SELECCIÓN DINÁMICA
        col1, col2 = st.columns(2)
        
        if 'sel_cli_idx' not in st.session_state: st.session_state.sel_cli_idx = 0
        if 'sel_rut_idx' not in st.session_state: st.session_state.sel_rut_idx = 0

        def update_price():
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
        precio_sugerido = float(df_rut.iloc[idx_rut]['tarifa_sugerida']) 

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


# --- H. IMPORTADOR MASIVO ---
elif menu == "Importador Masivo":
    st.header("📥 Importación Masiva desde Excel")
    st.markdown("Carga las guías de despacho (Tobar/Cosio). **El sistema creará las rutas nuevas si no existen (con 0 KM).**")

    df_cli, df_rut, df_con, df_cam = load_maestros()
    
    col_conf1, col_conf2 = st.columns(2)
    cliente_sel = col_conf1.selectbox("Seleccionar Cliente (Formato)", ["TOBAR", "COSIO"])
    
    id_cliente_bd = None
    if not df_cli.empty:
        match = df_cli[df_cli['nombre'].str.contains(cliente_sel, case=False, na=False)]
        if not match.empty:
            id_cliente_bd = match.iloc[0]['id_cliente']
            st.success(f"Vinculado a cliente BD: {match.iloc[0]['nombre']} (ID: {id_cliente_bd})")
        else:
            st.warning(f"⚠️ ¡Error! Cliente '{cliente_sel}' no encontrado. Por favor créalo en el módulo Clientes.")
            st.stop()

    uploaded_file = st.file_uploader("Subir archivo Excel (.xlsx / .xlsm)", type=["xlsx", "xlsm"])

    if uploaded_file and id_cliente_bd:
        try:
            viajes_a_cargar = []
            
            if cliente_sel == "TOBAR":
                # Header en fila 24 (índice 23)
                df_excel = pd.read_excel(uploaded_file, header=23) 
                df_excel = df_excel.dropna(subset=['FECHA']).copy()
                
                st.write("Vista Previa (Tobar):", df_excel.head())

                for index, row in df_excel.iterrows():
                    origen = str(row['DESDE']).strip()
                    destino = str(row['HASTA']).strip()
                    contenedor = f"{row['SIGLA CONTENEDOR']}{row['NUMERO CONTENEDOR']}"
                    monto = 0.0 
                    
                    id_ruta, _ = get_or_create_ruta(origen, destino)

                    viajes_a_cargar.append({
                        "fecha": row['FECHA'],
                        "id_cliente": id_cliente_bd,
                        "id_ruta": id_ruta,
                        "destino_raw": f"{origen} -> {destino}",
                        "observaciones": f"Contenedor: {contenedor}",
                        "monto": monto
                    })

            elif cliente_sel == "COSIO":
                # Header en fila 10 (índice 9)
                df_excel = pd.read_excel(uploaded_file, header=9)
                df_excel = df_excel.dropna(subset=['FECHA']).copy()
                
                st.write("Vista Previa (Cosio):", df_excel.head())

                for index, row in df_excel.iterrows():
                    origen = str(row['DESDE']).strip()
                    destino = str(row['HASTA']).strip()
                    monto_str = str(row['MONTO']).replace('$','').replace('.','').replace(',','')
                    try: monto = float(monto_str)
                    except: monto = 0.0
                    
                    id_ruta, _ = get_or_create_ruta(origen, destino)

                    viajes_a_cargar.append({
                        "fecha": row['FECHA'],
                        "id_cliente": id_cliente_bd,
                        "id_ruta": id_ruta,
                        "destino_raw": f"{origen} -> {destino}",
                        "observaciones": f"Contenedor: {row['CONTENEDOR']}",
                        "monto": monto
                    })

            # --- PREVISUALIZACIÓN Y CARGA ---
            st.markdown("### 🕵️‍♂️ Resumen de Viajes a Cargar")
            df_preview = pd.DataFrame(viajes_a_cargar)
            st.dataframe(df_preview, use_container_width=True)

            if st.button("✅ Procesar e Insertar Viajes en BD", type="primary"):
                count = 0
                with engine.begin() as conn:
                    for v in viajes_a_cargar:
                        sql = text("""
                            INSERT INTO "VIAJES" (fecha, id_cliente, id_ruta, estado, monto_neto, observaciones, id_conductor, id_camion)
                            VALUES (:f, :c, :r, 'Finalizado', :m, :o, NULL, NULL)
                        """)
                        conn.execute(sql, {
                            "f": v['fecha'], 
                            "c": v['id_cliente'], 
                            "r": v['id_ruta'], 
                            "m": v['monto'], 
                            "o": v['observaciones']
                        })
                        count += 1
                st.success(f"¡Éxito! Se cargaron {count} viajes y se crearon las rutas faltantes (si hubo).")
                load_maestros.clear()
                time.sleep(2)
                st.rerun()

        except Exception as e:
            st.error(f"Error procesando el archivo: {e}")