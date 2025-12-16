import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import time
from datetime import date

# ==========================================
# 1. CONFIGURACIÓN
# ==========================================
st.set_page_config(page_title="Atlis Logistics", page_icon="🚛", layout="wide")

try:
    DATABASE_URL = st.secrets["db"]["url"]
except:
    # Esto es solo por si se te olvida configurar el secreto, para que no falle feo
    st.error("No se encontró la URL de la base de datos en los secretos.")
    st.stop()

# ESTILOS (Modo Oscuro Corporativo + Mejoras UI)
st.markdown("""
<style>
    .stApp { background-color: #101922; color: #E2E8F0; }
    
    /* Métricas */
    div[data-testid="stMetric"] { background-color: #1A232E; border: 1px solid #2D3748; padding: 15px; border-radius: 8px; }
    div[data-testid="stMetricLabel"] { color: #94A3B8; font-size: 13px; font-weight: 500; }
    div[data-testid="stMetricValue"] { color: #FFFFFF; font-size: 24px; font-weight: 600; }
    
    /* Sidebar */
    section[data-testid="stSidebar"] { background-color: #0d1319; border-right: 1px solid #2D3748; }
    
    /* Botones Generales */
    div.stButton > button { border-radius: 6px; font-weight: 500; border: none; transition: 0.2s; }
    
    /* Botón Principal (Azul) */
    div.stButton > button[kind="secondary"] { background-color: #137fec; color: white; }
    div.stButton > button[kind="secondary"]:hover { background-color: #0f66bd; }
    
    /* Botón Peligro/Borrar (Rojo) */
    div.stButton > button[kind="primary"] { background-color: #dc2626; color: white; }
    
    /* Inputs y Tablas */
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
    st.error(f"Error de conexión: {e}")
    st.stop()

# ==========================================
# 2. MENÚ LATERAL
# ==========================================
with st.sidebar:
    st.title("LogisticsHub")
    st.caption("ERP de Transporte v6.0")
    st.markdown("---")
    menu = st.radio("Módulos", 
        ["Panel de Control", "Gestión de Flota", "Conductores", "Clientes", "Rutas", "Registrar Viaje"], 
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.info("💡 **Tip:** Use la pestaña 'Modificar' dentro de cada módulo para corregir datos.")

# ==========================================
# 3. LÓGICA DEL SISTEMA
# ==========================================

# --- A. PANEL DE CONTROL ---
if menu == "Panel de Control":
    st.header("Panel de Control Operativo")
    st.markdown("---")

    # KPIs en tiempo real
    try:
        with engine.connect() as conn:
            n_cam = pd.read_sql('SELECT COUNT(*) FROM "CAMIONES"', conn).iloc[0,0]
            n_via = pd.read_sql('SELECT COUNT(*) FROM "VIAJES"', conn).iloc[0,0]
            n_cli = pd.read_sql('SELECT COUNT(*) FROM "CLIENTE"', conn).iloc[0,0]
    except:
        n_cam, n_via, n_cli = 0, 0, 0

    c1, c2, c3 = st.columns(3)
    c1.metric("Flota Total", n_cam)
    c2.metric("Viajes Totales", n_via)
    c3.metric("Clientes Activos", n_cli)

    st.markdown("### 📋 Bitácora de Viajes")
    
    try:
        # Consulta maestra con todos los datos cruzados
        sql = """
            SELECT v.id_viaje, v.fecha, cl.nombre as cliente, c.patente, c.marca, co.nombre as conductor, r.destino, v.estado 
            FROM "VIAJES" v
            LEFT JOIN "CAMIONES" c ON v.id_camion = c.id_camion
            LEFT JOIN "CONDUCTORES" co ON v.id_conductor = co.id_conductor
            LEFT JOIN "RUTAS" r ON v.id_ruta = r.id_ruta
            LEFT JOIN "CLIENTE" cl ON v.id_cliente = cl.id_cliente
            ORDER BY v.fecha DESC
        """
        df_viajes = pd.read_sql(sql, engine)
        st.dataframe(df_viajes, use_container_width=True, hide_index=True)

        # SECCIÓN DE ELIMINACIÓN DE VIAJES
        if not df_viajes.empty:
            with st.expander("🗑️ Gestión: Eliminar Viaje Erróneo"):
                st.warning("Cuidado: Esta acción no se puede deshacer.")
                opts = {f"#{row['id_viaje']} | {row['fecha']} | {row['cliente']} -> {row['destino']}": row['id_viaje'] for i, row in df_viajes.iterrows()}
                sel_viaje = st.selectbox("Seleccione el viaje a eliminar", list(opts.keys()))
                
                if st.button("🔥 Confirmar Eliminación", type="primary"):
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM \"VIAJES\" WHERE id_viaje = :id"), {"id": opts[sel_viaje]})
                        st.toast("Viaje eliminado correctamente.", icon="✅")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al eliminar: {e}")

    except Exception as e:
        st.error(f"Error cargando panel: {e}")

# --- B. GESTIÓN DE FLOTA (CRUD COMPLETO) ---
elif menu == "Gestión de Flota":
    st.header("🚚 Inventario de Flota")
    
    # Pestañas para organizar Crear vs Modificar
    tab_new, tab_edit = st.tabs(["➕ Nuevo Vehículo", "✏️ Modificar / Eliminar"])
    
    # 1. CREAR
    with tab_new:
        with st.form("new_truck", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                pat = st.text_input("Patente *")
                marcas_list = ["Ford", "Kenworth", "International", "Freightliner", "Mack", "Peterbilt", "Volvo", "Scania", "Mercedes-Benz", "Volkswagen", "JAC", "Sinotruk", "Dongfeng", "Otro"]
                mar_sel = st.selectbox("Marca", marcas_list)
                if mar_sel == "Otro": mar_sel = st.text_input("Especifique Marca")
            with c2:
                mod = st.text_input("Modelo")
                ani = st.number_input("Año", 1990, 2030, 2024)
                ren = st.number_input("Rendimiento (Km/L)", 1.0, 10.0, 2.5)
            
            if st.form_submit_button("Guardar Vehículo", type="secondary"):
                if pat:
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("INSERT INTO \"CAMIONES\" (patente, marca, modelo, \"año\", rendimiento_esperado) VALUES (:p, :m, :mo, :a, :r)"),
                                         {"p": pat, "m": mar_sel, "mo": mod, "a": ani, "r": ren})
                        st.toast("Vehículo guardado", icon="✅")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
                else: st.warning("Falta Patente")

    # 2. MODIFICAR / ELIMINAR
    with tab_edit:
        try:
            df_cam = pd.read_sql('SELECT * FROM "CAMIONES" ORDER BY id_camion DESC', engine)
            if df_cam.empty:
                st.info("No hay vehículos registrados.")
            else:
                # Selector
                map_cam = {f"{r['patente']} - {r['marca']} {r['modelo']}": r['id_camion'] for i, r in df_cam.iterrows()}
                sel_cam_label = st.selectbox("Seleccione Vehículo a Editar", list(map_cam.keys()))
                id_sel = map_cam[sel_cam_label]
                
                # Obtener datos actuales
                row = df_cam[df_cam['id_camion'] == id_sel].iloc[0]
                
                st.markdown("#### Editar Datos")
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    # Pre-llenamos con los datos actuales
                    new_pat = st.text_input("Editar Patente", value=row['patente'])
                    new_mar = st.text_input("Editar Marca", value=row['marca'])
                    new_mod = st.text_input("Editar Modelo", value=row['modelo'])
                with col_e2:
                    new_ani = st.number_input("Editar Año", 1990, 2030, int(row['año']))
                    new_ren = st.number_input("Editar Rendimiento", 1.0, 10.0, float(row['rendimiento_esperado']))

                col_btn1, col_btn2 = st.columns([1, 4])
                if col_btn1.button("💾 Actualizar Datos", type="secondary"):
                    try:
                        with engine.begin() as conn:
                            sql_upd = text("""
                                UPDATE "CAMIONES" SET patente=:p, marca=:m, modelo=:mo, "año"=:a, rendimiento_esperado=:r 
                                WHERE id_camion=:id
                            """)
                            conn.execute(sql_upd, {"p": new_pat, "m": new_mar, "mo": new_mod, "a": new_ani, "r": new_ren, "id": id_sel})
                        st.toast("Datos actualizados correctamente", icon="🔄")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e: st.error(f"Error al actualizar: {e}")
                
                st.markdown("---")
                if st.button("🗑️ Eliminar este Vehículo", type="primary"):
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM \"CAMIONES\" WHERE id_camion = :id"), {"id": id_sel})
                        st.success("Vehículo eliminado.")
                        time.sleep(1)
                        st.rerun()
                    except: st.error("No se puede eliminar: Tiene viajes asociados. Borre los viajes primero.")

        except Exception as e: st.error(e)
        
    # Tabla General
    st.markdown("### Inventario Actual")
    try:
        st.dataframe(pd.read_sql('SELECT * FROM "CAMIONES"', engine), use_container_width=True, hide_index=True)
    except: pass

# --- C. CONDUCTORES (CRUD COMPLETO) ---
elif menu == "Conductores":
    st.header("👨‍✈️ Base de Conductores")
    tab_new, tab_edit = st.tabs(["➕ Nuevo Conductor", "✏️ Modificar / Eliminar"])

    with tab_new:
        with st.form("new_driver", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nombre Completo *")
                rut = st.text_input("RUT *")
            with c2:
                lic = st.selectbox("Licencia", ["A5", "A4", "A2", "A1"])
                act = st.checkbox("Activo", True)
            
            if st.form_submit_button("Guardar", type="secondary"):
                if nom and rut:
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("INSERT INTO \"CONDUCTORES\" (nombre, rut, licencia, activo) VALUES (:n, :r, :l, :a)"),
                                         {"n": nom, "r": rut, "l": lic, "a": act})
                        st.toast("Conductor registrado", icon="✅")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e: st.error(e)
                else: st.warning("Datos incompletos")

    with tab_edit:
        try:
            df_con = pd.read_sql('SELECT * FROM "CONDUCTORES" ORDER BY id_conductor DESC', engine)
            if not df_con.empty:
                map_con = {f"{r['nombre']} ({r['rut']})": r['id_conductor'] for i, r in df_con.iterrows()}
                sel_con_label = st.selectbox("Seleccione Conductor", list(map_con.keys()))
                id_sel = map_con[sel_con_label]
                row = df_con[df_con['id_conductor'] == id_sel].iloc[0]

                c_e1, c_e2 = st.columns(2)
                new_nom = c_e1.text_input("Editar Nombre", value=row['nombre'])
                new_rut = c_e1.text_input("Editar RUT", value=row['rut'])
                new_lic = c_e2.selectbox("Editar Licencia", ["A5", "A4", "A2", "A1"], index=["A5", "A4", "A2", "A1"].index(row['licencia']) if row['licencia'] in ["A5", "A4", "A2", "A1"] else 0)
                new_act = c_e2.checkbox("Conductor Activo", value=bool(row['activo']))

                if st.button("💾 Actualizar Conductor", type="secondary"):
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE \"CONDUCTORES\" SET nombre=:n, rut=:r, licencia=:l, activo=:a WHERE id_conductor=:id"),
                                     {"n": new_nom, "r": new_rut, "l": new_lic, "a": new_act, "id": id_sel})
                    st.toast("Actualizado", icon="🔄")
                    time.sleep(1)
                    st.rerun()
                
                st.markdown("---")
                if st.button("🗑️ Eliminar Conductor", type="primary"):
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM \"CONDUCTORES\" WHERE id_conductor=:id"), {"id": id_sel})
                        st.success("Eliminado")
                        time.sleep(1)
                        st.rerun()
                    except: st.error("No se puede eliminar: Tiene viajes asociados.")
        except: pass
    
    st.markdown("### Nómina")
    try:
        df = pd.read_sql('SELECT * FROM "CONDUCTORES"', engine)
        df["activo"] = df["activo"].apply(lambda x: "✅" if x else "🔴")
        st.dataframe(df, use_container_width=True, hide_index=True)
    except: pass

# --- D. CLIENTES (CRUD COMPLETO) ---
elif menu == "Clientes":
    st.header("🏢 Cartera de Clientes")
    tab_new, tab_edit = st.tabs(["➕ Nueva Empresa", "✏️ Modificar / Eliminar"])

    with tab_new:
        with st.form("new_cli", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                nom = st.text_input("Nombre Empresa *")
                rut = st.text_input("RUT Empresa")
            with c2:
                con = st.text_input("Contacto / Email")
            
            if st.form_submit_button("Guardar", type="secondary"):
                if nom:
                    try:
                        with engine.begin() as conn:
                            # QUERY ADAPTADA A TU TABLA 'CLIENTE'
                            conn.execute(text("INSERT INTO \"CLIENTE\" (nombre, rut_empresa, contacto) VALUES (:n, :r, :c)"),
                                         {"n": nom, "r": rut, "c": con})
                        st.toast("Cliente registrado", icon="✅")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e: st.error(e)
                else: st.warning("Nombre obligatorio")

    with tab_edit:
        try:
            df_cli = pd.read_sql('SELECT * FROM "CLIENTE" ORDER BY id_cliente DESC', engine)
            if not df_cli.empty:
                map_cli = {f"{r['nombre']}": r['id_cliente'] for i, r in df_cli.iterrows()}
                sel_cli_label = st.selectbox("Seleccione Cliente", list(map_cli.keys()))
                id_sel = map_cli[sel_cli_label]
                row = df_cli[df_cli['id_cliente'] == id_sel].iloc[0]

                c_e1, c_e2 = st.columns(2)
                new_nom = c_e1.text_input("Editar Nombre", value=row['nombre'])
                new_rut = c_e1.text_input("Editar RUT", value=row['rut_empresa'] if row['rut_empresa'] else "")
                new_con = c_e2.text_input("Editar Contacto", value=row['contacto'] if row['contacto'] else "")

                if st.button("💾 Actualizar Cliente", type="secondary"):
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE \"CLIENTE\" SET nombre=:n, rut_empresa=:r, contacto=:c WHERE id_cliente=:id"),
                                     {"n": new_nom, "r": new_rut, "c": new_con, "id": id_sel})
                    st.toast("Cliente Actualizado", icon="🔄")
                    time.sleep(1)
                    st.rerun()

                st.markdown("---")
                if st.button("🗑️ Eliminar Cliente", type="primary"):
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM \"CLIENTE\" WHERE id_cliente=:id"), {"id": id_sel})
                        st.success("Cliente eliminado")
                        time.sleep(1)
                        st.rerun()
                    except: st.error("No se puede eliminar: Tiene viajes asociados.")
        except: pass

    st.markdown("### Directorio")
    try:
        st.dataframe(pd.read_sql('SELECT * FROM "CLIENTE"', engine), use_container_width=True, hide_index=True)
    except: pass

# --- E. RUTAS (CRUD COMPLETO) ---
elif menu == "Rutas":
    st.header("🛣️ Rutas Comerciales")
    tab_new, tab_edit = st.tabs(["➕ Nueva Ruta", "✏️ Modificar / Eliminar"])

    with tab_new:
        with st.form("new_route", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                ori = st.text_input("Origen", "Santiago")
                des = st.text_input("Destino *")
            with c2:
                km = st.number_input("Distancia (Km)", 0, 5000, 100)
                tar = st.number_input("Tarifa Base ($)", 0, 10000000, 500000)
            
            if st.form_submit_button("Guardar", type="secondary"):
                try:
                    with engine.begin() as conn:
                        conn.execute(text("INSERT INTO \"RUTAS\" (origen, destino, km_estimados, tarifa_sugerida) VALUES (:o, :d, :k, :t)"),
                                     {"o": ori, "d": des, "k": km, "t": tar})
                    st.toast("Ruta creada", icon="✅")
                    time.sleep(1)
                    st.rerun()
                except: st.error("Error al guardar")

    with tab_edit:
        try:
            df_rut = pd.read_sql('SELECT * FROM "RUTAS" ORDER BY id_ruta DESC', engine)
            if not df_rut.empty:
                map_rut = {f"{r['origen']} -> {r['destino']}": r['id_ruta'] for i, r in df_rut.iterrows()}
                sel_rut_label = st.selectbox("Seleccione Ruta", list(map_rut.keys()))
                id_sel = map_rut[sel_rut_label]
                row = df_rut[df_rut['id_ruta'] == id_sel].iloc[0]

                c_e1, c_e2 = st.columns(2)
                new_ori = c_e1.text_input("Editar Origen", value=row['origen'])
                new_des = c_e1.text_input("Editar Destino", value=row['destino'])
                new_km = c_e2.number_input("Editar Km", 0, 5000, int(row['km_estimados']))
                new_tar = c_e2.number_input("Editar Tarifa", 0, 10000000, int(row['tarifa_sugerida']))

                if st.button("💾 Actualizar Ruta", type="secondary"):
                    with engine.begin() as conn:
                        conn.execute(text("UPDATE \"RUTAS\" SET origen=:o, destino=:d, km_estimados=:k, tarifa_sugerida=:t WHERE id_ruta=:id"),
                                     {"o": new_ori, "d": new_des, "k": new_km, "t": new_tar, "id": id_sel})
                    st.toast("Ruta Actualizada", icon="🔄")
                    time.sleep(1)
                    st.rerun()
                
                st.markdown("---")
                if st.button("🗑️ Eliminar Ruta", type="primary"):
                    try:
                        with engine.begin() as conn:
                            conn.execute(text("DELETE FROM \"RUTAS\" WHERE id_ruta=:id"), {"id": id_sel})
                        st.success("Ruta eliminada")
                        time.sleep(1)
                        st.rerun()
                    except: st.error("No se puede eliminar: Tiene viajes asociados.")
        except: pass

    st.markdown("### Tarifario")
    try:
        st.dataframe(pd.read_sql('SELECT * FROM "RUTAS"', engine), use_container_width=True, hide_index=True)
    except: pass

# --- F. REGISTRAR VIAJE ---
elif menu == "Registrar Viaje":
    st.header("🚀 Nueva Operación")

    # Cargar datos
    try:
        df_cam = pd.read_sql('SELECT id_camion, patente, marca FROM "CAMIONES"', engine)
        df_con = pd.read_sql('SELECT id_conductor, nombre FROM "CONDUCTORES" WHERE activo = true', engine)
        df_rut = pd.read_sql('SELECT id_ruta, destino, km_estimados FROM "RUTAS"', engine)
        df_cli = pd.read_sql('SELECT id_cliente, nombre FROM "CLIENTE"', engine)
    except:
        st.error("Error cargando maestros.")
        st.stop()

    if df_cam.empty or df_con.empty or df_rut.empty or df_cli.empty:
        st.warning("⚠️ Faltan datos maestros para crear un viaje.")
    else:
        with st.container():
            with st.form("form_viaje"):
                idx_cli = st.selectbox("Cliente Solicitante", df_cli.index, format_func=lambda x: df_cli.iloc[x]['nombre'])
                st.markdown("---")
                c1,c2 = st.columns(2)
                with c1:
                    idx_cam = st.selectbox("Vehículo", df_cam.index, format_func=lambda x: f"{df_cam.iloc[x]['patente']} - {df_cam.iloc[x]['marca']}")
                    idx_con = st.selectbox("Conductor", df_con.index, format_func=lambda x: df_con.iloc[x]['nombre'])
                    fec = st.date_input("Fecha Salida", date.today())
                with c2:
                    idx_rut = st.selectbox("Ruta", df_rut.index, format_func=lambda x: f"A {df_rut.iloc[x]['destino']} ({df_rut.iloc[x]['km_estimados']} km)")
                    est = st.selectbox("Estado", ["Programado", "En Ruta", "Finalizado"])

                st.markdown("---")
                if st.form_submit_button("Confirmar Viaje", type="secondary"):
                    try:
                        # IDs
                        v_cli = int(df_cli.iloc[idx_cli]['id_cliente'])
                        v_cam = int(df_cam.iloc[idx_cam]['id_camion'])
                        v_con = int(df_con.iloc[idx_con]['id_conductor'])
                        v_rut = int(df_rut.iloc[idx_rut]['id_ruta'])
                        
                        with engine.begin() as conn:
                            sql = text("""
                                INSERT INTO "VIAJES" (fecha, id_cliente, id_camion, id_conductor, id_ruta, estado, monto_neto)
                                VALUES (:f, :icl, :idc, :idco, :idr, :est, 0)
                            """)
                            conn.execute(sql, {"f": fec, "icl": v_cli, "idc": v_cam, "idco": v_con, "idr": v_rut, "est": est})
                        
                        st.balloons()
                        st.success("Operación Registrada Exitosamente")
                        time.sleep(2)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al registrar: {e}")