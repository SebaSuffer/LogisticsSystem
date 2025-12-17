import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import time

# ==========================================
# 1. CONFIGURACIÓN Y ESTILOS "GOOGLE STITCH"
# ==========================================
st.set_page_config(page_title="LogisticsHub", page_icon="🚛", layout="wide")

try:
    DATABASE_URL = st.secrets["db"]["url"]
except:
    st.error("No se encontró la URL de la base de datos.")
    st.stop()

# --- INYECCIÓN DE CSS (ESTILO DARK SLATE / TAILWIND) ---
st.markdown("""
<link href="https://fonts.googleapis.com/icon?family=Material+Icons+Outlined" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">

<style>
    /* 1. Fondo General y Fuentes */
    .stApp {
        background-color: #0F172A; /* Slate 900 */
        font-family: 'Inter', sans-serif;
    }
    
    /* 2. Ajustes de Texto */
    h1, h2, h3 { color: #F8FAFC !important; }
    p, label, span { color: #94A3B8 !important; }
    
    /* 3. Tarjetas KPI Personalizadas (CSS para imitar tu HTML) */
    .kpi-card {
        background-color: #1E293B; /* Slate 800 */
        border: 1px solid #334155;
        border-radius: 0.5rem;
        padding: 1.25rem;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        margin-bottom: 1rem;
    }
    .kpi-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .kpi-title {
        font-size: 0.875rem;
        font-weight: 500;
        color: #94A3B8;
    }
    .kpi-value {
        font-size: 1.875rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-bottom: 0.5rem;
    }
    .kpi-badge {
        display: inline-flex;
        align-items: center;
        padding: 0.125rem 0.5rem;
        border-radius: 0.25rem;
        font-size: 0.75rem;
        font-weight: 500;
    }
    .badge-green { background-color: rgba(22, 163, 74, 0.2); color: #4ADE80; }
    .badge-red { background-color: rgba(220, 38, 38, 0.2); color: #F87171; }
    
    /* 4. Inputs y Selectores */
    .stSelectbox > div > div {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        color: white !important;
    }
    
    /* 5. Tablas */
    div[data-testid="stDataFrame"] {
        border: 1px solid #334155;
        border-radius: 8px;
        background-color: #1E293B;
    }
</style>
""", unsafe_allow_html=True)

# ... (MANTÉN TU FUNCIÓN get_engine Y EL LOGIN IGUAL QUE ANTES) ...
@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL, pool_pre_ping=True)
try:
    engine = get_engine()
except Exception as e:
    st.error(f"❌ Error fatal: {e}")
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
# 3. MENÚ LATERAL (ACTUALIZADO)
# ==========================================
with st.sidebar:
    st.title("LogisticsHub")
    st.caption(f"Usuario: {st.session_state.usuario_activo}")
    st.markdown("---")
    
    if st.button("Cerrar Sesión"):
        st.session_state.usuario_activo = None
        st.rerun()
        
    st.markdown("---")
    
    # MENÚ DE NAVEGACIÓN
    menu = st.radio("Módulos ERP", 
        [
            "Dashboard", 
            "Historial de Viajes", 
            "Subir Archivos", 
            "Gestión de Flota", 
            "Conductores", 
            "Clientes", 
            "Rutas", 
            "Tarifarios"
        ], 
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    
    # --- NUEVA SECCIÓN: PARAMETROS DEL NEGOCIO ---
    # Esto define las variables que usa el Dashboard para calcular la plata
    st.markdown("### ⚙️ Configuración")
    with st.expander("💰 Costos & Variables", expanded=False):
        st.caption("Ajusta aquí los valores reales del negocio para el cálculo de utilidad.")
        
        # 1. Pago por vuelta (Trato informal)
        PAGO_CHOFER_POR_VUELTA = st.number_input("Pago Chofer por Vuelta ($)", value=10000, step=1000)
        
        # 2. Costo Legal (Imposiciones / Previred)
        COSTO_PREVIRED = st.number_input("Costo Previred Mensual ($)", value=106012, step=1000, help="Gasto fijo mensual por tener al chofer contratado.")
        
        # 3. IVA Petróleo (Para descontar impuestos)
        iva_input = st.number_input("% Recuperación IVA Petróleo", value=19, max_value=100)
        IVA_PETROLEO = iva_input / 100
    
    st.markdown("---")
    st.info("Sistema Operativo v10.2 (ERP Full)")

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
    if not origen_abbr or not destino_abbr or str(origen_abbr) == 'nan' or str(destino_abbr) == 'nan':
        return None, False

    origen_abbr = str(origen_abbr).strip().upper()
    destino_abbr = str(destino_abbr).strip().upper()
    
    df_rutas = pd.read_sql('SELECT id_ruta, origen, destino FROM "RUTAS"', engine)
    match = df_rutas[(df_rutas['origen'].str.upper() == origen_abbr) & (df_rutas['destino'].str.upper() == destino_abbr)]
    
    if not match.empty:
        return int(match.iloc[0]['id_ruta']), False
    
    try:
        with engine.begin() as conn:
            sql_insert = text('INSERT INTO "RUTAS" (origen, destino, km_estimados, tarifa_sugerida) VALUES (:o, :d, :k, 0) RETURNING id_ruta')
            result = conn.execute(sql_insert, {"o": origen_abbr, "d": destino_abbr, "k": 0}).fetchone()
            st.toast(f"Ruta creada: {origen_abbr} -> {destino_abbr}", icon="🆕")
            return int(result[0]), True
    except Exception as e:
        st.error(f"Error ruta: {e}")
        return None, True

def get_precio_automatico(id_cliente, id_ruta, df_rutas, df_tarifas):
    if id_ruta is None: return 0.0
    tarifa_match = df_tarifas[(df_tarifas['id_cliente'] == id_cliente) & (df_tarifas['id_ruta'] == id_ruta)]
    if not tarifa_match.empty: return float(tarifa_match.iloc[0]['monto_pactado'])
    ruta_match = df_rutas[df_rutas['id_ruta'] == id_ruta]
    if not ruta_match.empty: return float(ruta_match.iloc[0]['tarifa_sugerida'])
    return 0.0

def limpiar_monto_inteligente(valor_excel):
    if pd.isna(valor_excel): return 0.0
    if isinstance(valor_excel, (int, float)): return float(valor_excel)
    valor_str = str(valor_excel).strip().replace('$', '').strip()
    if ',' in valor_str: valor_str = valor_str.split(',')[0]
    valor_str = valor_str.replace('.', '')
    try: return float(valor_str)
    except: return 0.0

def existe_viaje(conn, fecha, id_cliente, id_ruta, contenedor):
    sql = text("""
        SELECT COUNT(*) FROM "VIAJES" 
        WHERE fecha = :f AND id_cliente = :c AND id_ruta = :r AND observaciones LIKE :obs
    """)
    res = conn.execute(sql, {"f": fecha, "c": id_cliente, "r": id_ruta, "obs": f"%{contenedor}%"}).fetchone()
    return res[0] > 0

def parse_ids_para_borrar(texto_input):
    ids = set()
    if not texto_input: return []
    partes = texto_input.split(',')
    for parte in partes:
        parte = parte.strip()
        if '-' in parte:
            try:
                inicio, fin = map(int, parte.split('-'))
                ids.update(range(inicio, fin + 1))
            except: pass
        elif parte.isdigit():
            ids.add(int(parte))
    return sorted(list(ids))

# ==========================================
# 5. MÓDULOS DE LA APP
# ==========================================

# ==========================================
# SECCIÓN DASHBOARD (DISEÑO GOOGLE STITCH)
# ==========================================
if menu == "Dashboard":
    
    # 1. ENCABEZADO Y TÍTULO
    st.markdown("""
    <div style="margin-bottom: 20px;">
        <h1 style="display: flex; align-items: center; gap: 10px; font-size: 26px;">
            <span style="font-size: 32px;">📊</span> Tablero de Control Logístico
        </h1>
    </div>
    """, unsafe_allow_html=True)

    # --- LÓGICA DE DATOS (MANTENIDA) ---
    try:
        with engine.connect() as conn:
            # Consultas SQL (Igual que antes)
            df_ingresos = pd.read_sql(text("""
                SELECT v.fecha, 'INGRESO' as tipo_movimiento,
                c.nombre || ' - ' || r.origen || '->' || r.destino as detalle,
                v.monto_neto as monto, v.estado
                FROM "VIAJES" v
                LEFT JOIN "CLIENTE" c ON v.id_cliente = c.id_cliente
                LEFT JOIN "RUTAS" r ON v.id_ruta = r.id_ruta
            """), conn)
            
            df_egresos = pd.read_sql(text("""
                SELECT fecha, 'EGRESO' as tipo_movimiento,
                descripcion as detalle, monto, tipo_gasto, 'Pagado' as estado
                FROM "GASTOS"
            """), conn)
            
            # Conversión de fechas
            if not df_ingresos.empty: df_ingresos['fecha'] = pd.to_datetime(df_ingresos['fecha'])
            if not df_egresos.empty: df_egresos['fecha'] = pd.to_datetime(df_egresos['fecha'])

    except Exception as e:
        st.error(f"Error BD: {e}")
        st.stop()

    # 2. FILTROS (ESTILO MODERNO)
    col_filter_title, col_y, col_m = st.columns([2, 1, 1])
    with col_filter_title:
        st.markdown("""
        <div style="display: flex; align-items: center; gap: 8px; margin-top: 25px;">
            <span class="material-icons-outlined" style="color: #3B82F6;">calendar_month</span>
            <span style="font-size: 18px; font-weight: 600; color: #F8FAFC;">Filtros de Tiempo</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Lógica de fechas
    todas_fechas = pd.concat([df_ingresos['fecha'], df_egresos['fecha']])
    anios = sorted(todas_fechas.dt.year.unique(), reverse=True) if not todas_fechas.empty else [date.today().year]
    
    filtro_anio = col_y.selectbox("Año", ["Todos"] + list(anios))
    
    filtro_mes = "Todos"
    if filtro_anio != "Todos":
        meses = {1:"Enero", 2:"Febrero", 3:"Marzo", 4:"Abril", 5:"Mayo", 6:"Junio", 7:"Julio", 8:"Agosto", 9:"Septiembre", 10:"Octubre", 11:"Noviembre", 12:"Diciembre"}
        filtro_mes = col_m.selectbox("Mes", ["Todos"] + list(meses.values()))

    # --- FILTRADO DE DATAFRAMES ---
    df_in = df_ingresos.copy()
    df_out = df_egresos.copy()
    
    if filtro_anio != "Todos":
        df_in = df_in[df_in['fecha'].dt.year == filtro_anio]
        df_out = df_out[df_out['fecha'].dt.year == filtro_anio]
        if filtro_mes != "Todos":
            mes_idx = list(meses.keys())[list(meses.values()).index(filtro_mes)]
            df_in = df_in[df_in['fecha'].dt.month == mes_idx]
            df_out = df_out[df_out['fecha'].dt.month == mes_idx]

    # --- CÁLCULOS MATEMÁTICOS (TU LÓGICA) ---
    total_ingresos = df_in['monto'].sum() if not df_in.empty else 0
    total_viajes = len(df_in)
    
    # Costo Chofer
    costo_var = total_viajes * PAGO_CHOFER_POR_VUELTA
    meses_calc = 1 if (filtro_anio != "Todos" and filtro_mes != "Todos") else (pd.concat([df_in['fecha'], df_out['fecha']]).dt.to_period('M').nunique() if not df_in.empty else 0)
    costo_fijo = COSTO_PREVIRED * meses_calc
    total_chofer = costo_var + costo_fijo
    
    # Combustible y Otros
    gasto_petroleo = 0
    otros = 0
    if not df_out.empty:
        mask_pet = (df_out['tipo_gasto'] == 'VARIABLE') & (df_out['detalle'].str.contains('PETRÓLEO', case=False, na=False))
        gasto_petroleo = df_out[mask_pet]['monto'].sum()
        otros = df_out[~mask_pet]['monto'].sum()
        
    iva_recuperado = gasto_petroleo * IVA_PETROLEO
    petroleo_real = gasto_petroleo - iva_recuperado
    
    egresos_totales = total_chofer + petroleo_real + otros
    utilidad = total_ingresos - egresos_totales
    margen = (utilidad / total_ingresos * 100) if total_ingresos > 0 else 0

    st.markdown("---")

    # 3. TARJETAS KPI (DISEÑO HTML PERSONALIZADO)
    # Función para generar HTML de tarjeta
    def kpi_card(title, icon, value, subtext="", color_icon="#3B82F6", trend_positive=True):
        color_trend = "badge-green" if trend_positive else "badge-red"
        icon_trend = "arrow_upward" if trend_positive else "arrow_downward"
        
        return f"""
        <div class="kpi-card">
            <div class="kpi-header">
                <span class="material-icons-outlined" style="font-size: 20px; color: {color_icon};">{icon}</span>
                <span class="kpi-title">{title}</span>
            </div>
            <div class="kpi-value">{value}</div>
            <div class="{color_trend} kpi-badge">
                <span class="material-icons-outlined" style="font-size: 12px; margin-right: 4px;">{icon_trend}</span>
                {subtext}
            </div>
        </div>
        """

    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.markdown(kpi_card(
            "Utilidad Neta", "paid", f"${utilidad:,.0f}", 
            f"Margen {margen:.1f}%", color_icon="#F59E0B", trend_positive=(utilidad>0)
        ), unsafe_allow_html=True)
        
    with c2:
        # Viajes no tiene trend, usamos un placeholder visual
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-header">
                <span class="material-icons-outlined" style="font-size: 20px; color: #10B981;">local_shipping</span>
                <span class="kpi-title">Viajes Realizados</span>
            </div>
            <div class="kpi-value">{total_viajes}</div>
            <div class="kpi-badge" style="background-color: rgba(59, 130, 246, 0.1); color: #60A5FA;">
                <span class="material-icons-outlined" style="font-size: 12px; margin-right: 4px;">info</span>
                Operación activa
            </div>
        </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown(kpi_card(
            "Egresos Totales", "payments", f"${egresos_totales:,.0f}", 
            "Gastos operativos", color_icon="#EF4444", trend_positive=False
        ), unsafe_allow_html=True)
        
    with c4:
        st.markdown(kpi_card(
            "IVA Recuperado", "receipt_long", f"${iva_recuperado:,.0f}", 
            "Ahorro Fiscal", color_icon="#3B82F6", trend_positive=True
        ), unsafe_allow_html=True)

    # 4. GRÁFICOS (ESTILO PLOTLY PARA FONDO OSCURO)
    st.markdown("<h3 style='margin-top: 30px; margin-bottom: 20px; color: #F8FAFC;'>📈 Análisis Gráfico</h3>", unsafe_allow_html=True)
    
    tab_flow, tab_cost = st.tabs(["📊 Flujo de Caja", "🍩 Estructura de Costos"])

    # --- GRÁFICO BARRAS ---
    with tab_flow:
        df_graph = pd.DataFrame()
        if not df_in.empty:
            g_in = df_in.groupby(pd.Grouper(key='fecha', freq='M'))['monto'].sum().reset_index()
            g_in['Tipo'] = 'Ingresos'
            df_graph = pd.concat([df_graph, g_in])
        
        if not df_out.empty:
            g_out = df_out.groupby(pd.Grouper(key='fecha', freq='M'))['monto'].sum().reset_index()
            # Sumamos costo fijo visualmente
            g_out['monto'] += COSTO_PREVIRED
            g_out['Tipo'] = 'Egresos'
            df_graph = pd.concat([df_graph, g_out])

        if not df_graph.empty:
            # Colores EXACTOS de tu diseño HTML
            color_map = {"Ingresos": "#2dd4bf", "Egresos": "#fb7185"} # Teal y Rose
            
            fig = px.bar(df_graph, x="fecha", y="monto", color="Tipo", barmode="group",
                         color_discrete_map=color_map)
            
            # Personalización TOTAL para que parezca Chart.js del diseño
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(30, 41, 59, 1)', # Slate 800
                font=dict(color="#94A3B8", family="Inter"),
                margin=dict(t=20, l=20, r=20, b=20),
                legend=dict(title=None, orientation="h", y=1.02, x=1),
                xaxis=dict(showgrid=False, title=None),
                yaxis=dict(showgrid=True, gridcolor="#334155", title=None)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sin datos para graficar.")

    # --- GRÁFICO DONA ---
    with tab_cost:
        labels = ["Chofer (Sueldo+Bonos)", "Combustible (Neto)", "Otros"]
        values = [total_chofer, petroleo_real, otros]
        
        # Filtramos ceros
        data_pie = {"Item": [], "Monto": []}
        for l, v in zip(labels, values):
            if v > 0:
                data_pie["Item"].append(l)
                data_pie["Monto"].append(v)
        
        if data_pie["Monto"]:
            # Colores EXACTOS de tu diseño HTML
            colors_pie = ['#7dd3fc', '#fcd34d', '#fca5a5'] # Light Blue, Amber, Pink
            
            fig_pie = go.Figure(data=[go.Pie(
                labels=data_pie["Item"], 
                values=data_pie["Monto"], 
                hole=.6, # Dona grande como en el diseño
                marker=dict(colors=colors_pie, line=dict(color='#1E293B', width=2))
            )])
            
            fig_pie.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(30, 41, 59, 1)', # Slate 800
                font=dict(color="#94A3B8", family="Inter"),
                margin=dict(t=20, l=20, r=20, b=20),
                legend=dict(orientation="h", y=-0.1)
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Sin costos registrados.")

# --- HISTORIAL DE VIAJES ---
elif menu == "Historial de Viajes":
    st.header("🗂️ Administrador de Viajes (Ingresos)")
    try:
        sql_full = """
            SELECT 
                v.id_viaje, v.fecha, c.nombre as cliente, r.origen, r.destino, 
                v.monto_neto as tarifa, v.observaciones, v.estado
            FROM "VIAJES" v
            LEFT JOIN "CLIENTE" c ON v.id_cliente = c.id_cliente
            LEFT JOIN "RUTAS" r ON v.id_ruta = r.id_ruta
            ORDER BY v.id_viaje DESC
        """
        df_viajes = pd.read_sql(sql_full, engine)
        st.dataframe(df_viajes, use_container_width=True)
        
        st.markdown("---")
        st.subheader("🗑️ Eliminación Masiva de Viajes")
        col_del1, col_del2 = st.columns([2, 1])
        input_ids = col_del1.text_input("IDs a eliminar (ej: 10, 12-15, 20):")
        
        if col_del2.button("🗑️ Eliminar Seleccionados", type="primary"):
            ids_a_borrar = parse_ids_para_borrar(input_ids)
            if not ids_a_borrar:
                st.warning("Escribe IDs válidos.")
            else:
                try:
                    with engine.begin() as conn:
                        ids_tuple = f"({ids_a_borrar[0]})" if len(ids_a_borrar) == 1 else str(tuple(ids_a_borrar))
                        result = conn.execute(text(f'DELETE FROM "VIAJES" WHERE id_viaje IN {ids_tuple}'))
                        rows_deleted = result.rowcount
                    if rows_deleted > 0:
                        st.success(f"✅ {rows_deleted} viajes eliminados.")
                        time.sleep(1.5)
                        st.rerun()
                    else: st.warning("No se encontraron esos IDs.")
                except Exception as e: st.error(f"Error al eliminar: {e}")
    except Exception as e: st.error(f"Error cargando historial: {e}")

# ==========================================
# MÓDULO UNIFICADO: SUBIR ARCHIVOS (VIAJES Y GASTOS)
# ==========================================
elif menu == "Subir Archivos":
    st.header("📂 Centro de Carga de Archivos")
    st.caption("Selecciona el tipo de información que deseas subir al sistema.")

    tab_viajes, tab_gastos = st.tabs(["🚛 Cargar Viajes", "💸 Cargar Gastos"])

    # ---------------------------------------------------------
    # PESTAÑA 1: CARGAR VIAJES
    # ---------------------------------------------------------
    with tab_viajes:
        st.subheader("Cargar Viajes (Ingresos)")
        df_cli, df_rut, _, _, df_tar = load_maestros()
        
        col_conf1, col_conf2 = st.columns(2)
        formato_sel = col_conf1.selectbox("Formato de Archivo", ["Formato TOBAR", "Formato COSIO"])
        
        if not df_cli.empty:
            idx_cliente_destino = col_conf2.selectbox("Asignar a Cliente (BD):", df_cli.index, format_func=lambda x: df_cli.iloc[x]['nombre'])
            id_cliente_bd = int(df_cli.iloc[idx_cliente_destino]['id_cliente'])
            nombre_cliente_bd = df_cli.iloc[idx_cliente_destino]['nombre']
        else:
            st.error("No hay clientes registrados en la BD.")
            st.stop()

        uploaded_viajes = st.file_uploader("Subir Excel de Viajes", type=["xlsx", "xlsm"], key="up_viajes")

        if uploaded_viajes and id_cliente_bd:
            try:
                viajes_a_cargar = []
                if formato_sel == "Formato TOBAR":
                    # CORRECCIÓN 1: Cambiamos "A:G" por "A:H"
                    # Esto obliga a Pandas a leer hasta la columna H, donde realmente está "HASTA"
                    df_excel = pd.read_excel(uploaded_viajes, header=23, usecols="A:H")
                    
                    # Limpieza estándar de cabeceras
                    df_excel.columns = df_excel.columns.str.strip().str.upper()
                    
                    # CORRECCIÓN 2: Eliminamos la columna "fantasma" (F) que se crea por el espacio doble
                    # Pandas suele llamarla "UNNAMED: 5". La borramos para limpiar el DF.
                    df_excel = df_excel.loc[:, ~df_excel.columns.str.contains('^UNNAMED')]

                    # Validación de seguridad
                    if 'HASTA' not in df_excel.columns:
                         st.error(f"⚠️ Aún no veo la columna HASTA. Columnas leídas: {df_excel.columns.tolist()}")
                         st.stop()

                    df_excel = df_excel.dropna(subset=['FECHA']).copy()
                    
                    for index, row in df_excel.iterrows():
                        # Ahora DESDE y HASTA coincidirán correctamente con las columnas G y H
                        origen = str(row['DESDE']).strip()
                        destino = str(row['HASTA']).strip() 
                        
                        contenedor = f"{row['SIGLA CONTENEDOR']} {row['NUMERO CONTENEDOR']}"
                        id_ruta, created = get_or_create_ruta(origen, destino)
                        precio = get_precio_automatico(id_cliente_bd, id_ruta, df_rut, df_tar) 
                        
                        viajes_a_cargar.append({
                            "fecha": row['FECHA'], 
                            "id_cliente": id_cliente_bd, 
                            "cliente_nombre": nombre_cliente_bd, 
                            "id_ruta": id_ruta, 
                            "ruta_nombre": f"{origen} -> {destino}", 
                            "observaciones": f"Contenedor: {contenedor}", 
                            "monto": precio
                        })

                elif formato_sel == "Formato COSIO":
                    df_excel = pd.read_excel(uploaded_viajes, header=9, usecols="A:G")
                    df_excel = df_excel.dropna(subset=['FECHA']).copy()
                    for index, row in df_excel.iterrows():
                        origen = str(row['DESDE']).strip()
                        destino = str(row['HASTA']).strip()
                        contenedor = str(row['CONTENEDOR']).strip()
                        id_ruta, created = get_or_create_ruta(origen, destino)
                        monto_excel = limpiar_monto_inteligente(row['MONTO'])
                        if monto_excel == 0: 
                            monto_excel = get_precio_automatico(id_cliente_bd, id_ruta, df_rut, df_tar)
                        viajes_a_cargar.append({"fecha": row['FECHA'], "id_cliente": id_cliente_bd, "cliente_nombre": nombre_cliente_bd, "id_ruta": id_ruta, "ruta_nombre": f"{origen} -> {destino}", "observaciones": f"Contenedor: {contenedor}", "monto": monto_excel})

                if viajes_a_cargar:
                    st.info(f"✅ Se detectaron {len(viajes_a_cargar)} viajes.")
                    with st.expander("Ver detalle de datos a cargar", expanded=False):
                        st.dataframe(pd.DataFrame(viajes_a_cargar)[['fecha', 'ruta_nombre', 'monto', 'observaciones']], use_container_width=True)

                    if st.button("Confirmar e Importar Viajes", type="primary", key="btn_viajes"):
                        count = 0
                        skip_count = 0
                        with engine.begin() as conn:
                            for v in viajes_a_cargar:
                                if existe_viaje(conn, v['fecha'], v['id_cliente'], v['id_ruta'], v['observaciones']):
                                    skip_count += 1
                                    continue
                                try:
                                    sql = text('INSERT INTO "VIAJES" (fecha, id_cliente, id_ruta, estado, monto_neto, observaciones) VALUES (:f, :c, :r, \'Finalizado\', :m, :o)')
                                    conn.execute(sql, {"f": v['fecha'], "c": int(v['id_cliente']), "r": int(v['id_ruta']), "m": float(v['monto']), "o": str(v['observaciones'])})
                                    count += 1
                                except Exception as row_error: st.error(f"Error: {row_error}")
                        if count > 0: st.success(f"¡Éxito! {count} viajes importados.")
                        if skip_count > 0: st.warning(f"Se omitieron {skip_count} duplicados.")
                        time.sleep(2)
                        st.rerun()
                else: st.warning("El archivo no contiene filas válidas.")
            except Exception as e: st.error(f"Error procesando viajes: {e}")

    # ---------------------------------------------------------
    # PESTAÑA 2: CARGAR GASTOS (CORREGIDO Y CON FILTRO INTELIGENTE)
    # ---------------------------------------------------------
    with tab_gastos:
        st.subheader("Cargar Gastos (E.E.F.F)")
        st.caption("Sube tu Excel de Estados Financieros. Buscamos la hoja 'input_costos'.")

        uploaded_gastos = st.file_uploader("Cargar Excel Gastos (.xlsx)", type=["xlsx", "xlsm"], key="up_gastos")

        if uploaded_gastos:
            try:
                try:
                    df_gastos = pd.read_excel(uploaded_gastos, sheet_name='input_costos')
                except ValueError:
                    st.error("❌ No se encontró la hoja 'input_costos'.")
                    st.stop()

                # Limpieza de cabeceras
                df_gastos.columns = df_gastos.columns.str.strip().str.upper()
                
                # Validación básica
                if 'FECHA' not in df_gastos.columns or 'MONTO' not in df_gastos.columns:
                    st.error("❌ Faltan columnas FECHA y MONTO en el Excel.")
                    st.stop()

                df_gastos = df_gastos.dropna(subset=['FECHA', 'MONTO']).copy()
                gastos_a_cargar = []
                omitidos_sueldo = 0
                
                for index, row in df_gastos.iterrows():
                    # 1. Limpieza de datos
                    detalle_valor = str(row['DETALLE']).strip() if 'DETALLE' in df_gastos.columns else "Sin detalle"
                    detalle_upper = detalle_valor.upper()
                    
                    # 2. FILTRO INTELIGENTE: Ignorar Sueldos manuales
                    # Como el Dashboard calcula el costo chofer automático, si subimos esto se duplica.
                    if "SUELDO" in detalle_upper or "IMPOSICIONES" in detalle_upper or "PREVIRED" in detalle_upper:
                        omitidos_sueldo += 1
                        continue 

                    monto_clean = limpiar_monto_inteligente(row['MONTO'])
                    
                    if monto_clean > 0:
                        tipo_valor = row['CATEGORIA'] if 'CATEGORIA' in df_gastos.columns else "GASTO GENERAL"
                        
                        gastos_a_cargar.append({
                            "fecha": row['FECHA'],
                            "tipo": str(tipo_valor), # Esto irá a la columna 'tipo_gasto'
                            "descripcion": detalle_valor,
                            "monto": monto_clean,
                            "proveedor": detalle_valor # Usamos el mismo detalle como proveedor por ahora
                        })

                if gastos_a_cargar:
                    st.info(f"✅ Se detectaron {len(gastos_a_cargar)} gastos válidos.")
                    
                    if omitidos_sueldo > 0:
                        st.warning(f"🛡️ Se omitieron {omitidos_sueldo} filas de 'Sueldo/Imposiciones' para evitar duplicar costos (el sistema ya los calcula automáticos).")

                    with st.expander("Ver detalle de gastos a cargar", expanded=False):
                        st.dataframe(pd.DataFrame(gastos_a_cargar), use_container_width=True)

                    if st.button("Confirmar e Importar Gastos", type="primary", key="btn_gastos"):
                        count = 0
                        with engine.begin() as conn:
                            for g in gastos_a_cargar:
                                try:
                                    # Insertamos en la columna 'tipo_gasto' que acabamos de crear
                                    sql = text('INSERT INTO "GASTOS" (fecha, tipo_gasto, descripcion, monto, proveedor) VALUES (:f, :t, :d, :m, :p)')
                                    conn.execute(sql, {"f": g['fecha'], "t": g['tipo'], "d": g['descripcion'], "m": g['monto'], "p": g['proveedor']})
                                    count += 1
                                except Exception as row_error: st.error(f"Error fila {count+1}: {row_error}")
                        
                        if count > 0:
                            st.success(f"¡Listo! {count} gastos registrados correctamente.")
                            time.sleep(2)
                            st.rerun()
                else:
                    if omitidos_sueldo > 0:
                        st.warning("El archivo solo contenía Sueldos/Imposiciones y fueron omitidos para evitar duplicidad.")
                    else:
                        st.warning("No se encontraron filas válidas para cargar.")
                        
            except Exception as e:
                st.error(f"Error procesando gastos: {e}")

# --- RESTO DE MÓDULOS (FLOTA, ETC) ---
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
                            conn.execute(text("INSERT INTO \"CAMIONES\" (patente, marca, modelo, \"año\", rendimiento_esperado) VALUES (:p, :m, :mo, :a, :r)"), {"p": pat, "m": marca, "mo": mod, "a": ani, "r": rend})
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
                        conn.execute(text("UPDATE \"CONDUCTORES\" SET nombre=:n, activo=:a WHERE id_conductor=:id"), {"n": n_nom, "a": n_act, "id": id_sel})
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

elif menu == "Clientes":
    st.header("🏢 Clientes")
    tab_new, tab_edit = st.tabs(["➕ Registrar", "✏️ Modificar / Eliminar"])
    with tab_new:
        with st.form("cli_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nom = c1.text_input("Nombre Empresa")
            rut = c2.text_input("RUT Empresa")
            con = st.text_input("Contacto")
            if st.form_submit_button("Guardar Cliente"):
                with engine.begin() as conn:
                    conn.execute(text("INSERT INTO \"CLIENTE\" (nombre, rut_empresa, contacto) VALUES (:n, :r, :c)"), {"n": nom, "r": rut, "c": con})
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
                    conn.execute(text("INSERT INTO \"RUTAS\" (origen, destino, km_estimados, tarifa_sugerida) VALUES (:o, :d, :k, :t)"), {"o": ori, "d": des, "k": km, "t": tar})
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
                    conn.execute(text("UPDATE \"RUTAS\" SET origen=:o, destino=:d, km_estimados=:k, tarifa_sugerida=:t WHERE id_ruta=:id"), {"o": n_ori, "d": n_des, "k": n_km, "t": n_tar, "id": id_sel})
                st.toast("Actualizado")
                time.sleep(1)
                st.rerun()
            if st.button("Eliminar Ruta"):
                with engine.begin() as conn:
                    conn.execute(text("DELETE FROM \"RUTAS\" WHERE id_ruta=:id"), {"id": id_sel})
                st.rerun()
        st.dataframe(df_rutas, use_container_width=True)

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
                    sql = text("INSERT INTO \"TARIFAS\" (id_cliente, id_ruta, monto_pactado) VALUES (:c, :r, :m) ON CONFLICT (id_cliente, id_ruta) DO UPDATE SET monto_pactado = EXCLUDED.monto_pactado")
                    conn.execute(sql, {"c": cli_id, "r": rut_id, "m": precio})
                st.success("Tarifa guardada")
            except Exception as e: st.error(f"Error: {e}")
    st.dataframe(pd.read_sql('SELECT * FROM "TARIFAS"', engine), use_container_width=True)