import os
import os
from playwright.sync_api import sync_playwright

import os
import pandas as pd
import psycopg2
from datetime import date
from dotenv import load_dotenv
import glob
import hashlib
from datetime import datetime
import re, tempfile, pythoncom, win32com.client as win32


import os
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright
from login import get_context

SESSIONS = {
    "facebook": {
        "url": "https://www.facebook.com/login",
        "file": "fb_session.json"
    },
    "instagram": {
        "url": "https://www.instagram.com/?flo=true",
        "file": "ig_session.json"
    },
    "tiktok": {
        "url": "https://www.tiktok.com/login/phone-or-email/email",
        "file": "tiktok_session.json"
    },
    "linkedin": {
        "url": "https://www.linkedin.com/login",
        "file": "linkedin_session.json"
    }
}

def get_context(playwright, platform: str):
    """
    Devuelve un browser, context y page logueados en la plataforma indicada.
    - platform: "facebook", "instagram", "tiktok", "linkedin"
    """
    if platform not in SESSIONS:
        raise ValueError(f"Plataforma no soportada: {platform}")

    session_info = SESSIONS[platform]
    session_file = session_info["file"]
    url = session_info["url"]

    browser = playwright.chromium.launch(headless=False)

    if not os.path.exists(session_file):
        # Primera vez: login manual
        context = browser.new_context()
        page = context.new_page()
        page.goto(url)

        print(f"Inicia sesión manualmente en {platform}")
        page.wait_for_timeout(120000)

        context.storage_state(path=session_file)
        print(f"Sesión de {platform} guardada en {session_file}")
    else:
        context = browser.new_context(storage_state=session_file)
        page = context.new_page()

        if platform == "linkedin":
            # Ir directo al panel de DATAX
            page.goto("https://www.linkedin.com/company/1283307/admin/analytics/updates/")
        else:
            page.goto(url.replace("/login", ""))

        print(f"Sesión de {platform} cargada desde {session_file}")

    return browser, context, page

# DESCARGA AUTOMATIZADA
OUTPUT_DIR = "linkedin_exports"

if len(sys.argv) < 4:
    print("Uso: python linkedin.py YYYY-MM-DD YYYY-MM-DD [Contenido|Visitantes|Seguidores|all]")
    sys.exit(1)
start_date_arg = sys.argv[1]
end_date_arg = sys.argv[2]
tabs_arg = sys.argv[3]
# Formato DD/MM/YYYY
start_date = datetime.strptime(start_date_arg, "%Y-%m-%d").strftime("%d/%m/%Y")
end_date = datetime.strptime(end_date_arg, "%Y-%m-%d").strftime("%d/%m/%Y")
# Pestañas según argumento
if tabs_arg.lower() == "all":
    tabs = ["Contenido", "Visitantes", "Seguidores"]
else:
    tabs = [tabs_arg]
# Loguin + Descarga 
with sync_playwright() as p:
    browser, context, page = get_context(p, "linkedin")
    #page.goto("https://www.linkedin.com/company/1283307/admin/analytics/updates/")
    
    #Descarga de csvs por pestaña
    def download_tab(page, tab_text: str, start_date: str, end_date: str):
        print(f"Descargando {tab_text}...")
        try:
            page.click(f"[data-test-org-menu-item__title]:has-text('{tab_text}')")
        except:
            page.click(f"text={tab_text}")
        page.wait_for_timeout(2000)  # simular cambio de pestaña
        # Esperar Primer botón "Exportar"
        page.wait_for_selector("button:has([data-test-icon='download-small'])", timeout=10000)
        # Seleccionar fechas personalizadas
        page.click("button[aria-label^='Periodo:']")
        page.wait_for_selector("div.member-analytics-addon-daterange-picker__dropdown-content-redesign")
        page.click("div.member-analytics-addon-daterange-picker__dropdown-content-redesign >> text=Personalizado")
        page.wait_for_timeout(2000)
        #contenedor principal del datepicker
        picker = page.locator("div.member-analytics-addon-daterange-picker__dropdown-content-redesign")
        # Buscar inputs de fecha dentro del picker
        start_input = picker.locator("input").nth(0)
        end_input = picker.locator("input").nth(1)
        # limpiar y escribir fechas
        start_input.fill(start_date)
        end_input.fill(end_date)
        #Boton Actualizar
        picker.locator("button:has-text('Actualizar')").click()
        page.wait_for_timeout(2000)
        # verificar error de rango
        if page.locator("text=Una o más fechas no están disponibles").is_visible():
            print("Rango erróneo, se usará 'Últimos 90 días'")
            page.click("div.member-analytics-addon-daterange-picker__dropdown-content-redesign >> text=Últimos 90 días")
            page.wait_for_timeout(1000)
        with page.expect_download() as download_info:
            # click boton1 de exportar
            page.click("button:has([data-test-icon='download-small'])")
            # esperar segundo boton de exportar
            page.wait_for_selector("button.artdeco-button--primary span:has-text('Exportar')", timeout=10000)
            page.wait_for_timeout(2000)
            #click segundo boton de exportar
            page.click("button.artdeco-button--primary span:has-text('Exportar')")
        download = download_info.value
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        # Nombre con rango de fechas
        file_name = f"{tab_text}_{start_date_arg}_{end_date_arg}.xls"
        file_path = os.path.join(OUTPUT_DIR, file_name)
        download.save_as(file_path)
        print(f"Guardado en {file_path}")
    #inicia descarga
    for tab in tabs:
        download_tab(page, tab, start_date, end_date)
    input("\nPresiona ENTER para cerrar...")
    browser.close()

# INGESTA LIKEDIN

# Configuración
load_dotenv()
PG_URL = os.getenv("PG_URL")
PAGE_ID = os.getenv("LI_PAGE_ID", "PAGE_ID_DEFAULT")

conn = psycopg2.connect(PG_URL)
cur = conn.cursor()

EXPORTS_DIR = "linkedin_exports"
CLEAN_DIR = "linkedin_clean"
LOG_DIR = "logs"
os.makedirs(CLEAN_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Función para IDs estables
def generar_pub_id(row):
    enlace = str(row.get("Enlace de la publicación") or "").strip().lower()
    if not enlace:
        enlace = f"{row.get('Fecha de creación')}_{row.get('Título de la publicación')}"
    return hashlib.sha1(enlace.encode("utf-8")).hexdigest()

# Limpieza por rango real
def limpiar_rangos_previos():
    LOG_FILE = os.path.join(LOG_DIR, "ingesta_log.txt")
    print("\n Verificando rango real de fechas a limpiar...")

    indicadores_csv = os.path.join(CLEAN_DIR, "Contenido_Indicadores.csv")
    publicaciones_csv = os.path.join(CLEAN_DIR, "Contenido_Publicaciones.csv")

    fechas = []
    origen = None

    try:
        if os.path.exists(indicadores_csv):
            df = pd.read_csv(indicadores_csv)
            if "Fecha" in df.columns:
                fechas = pd.to_datetime(df["Fecha"], errors="coerce").dropna().dt.date.tolist()
                origen = "Contenido_Indicadores.csv"
        elif os.path.exists(publicaciones_csv):
            df = pd.read_csv(publicaciones_csv)
            if "Fecha de creación" in df.columns:
                fechas = pd.to_datetime(df["Fecha de creación"], errors="coerce").dropna().dt.date.tolist()
                origen = "Contenido_Publicaciones.csv"
    except Exception as e:
        print(f" No se pudo leer fechas reales: {e}")
        return

    if not fechas:
        print(" No se detectaron fechas válidas, omitiendo limpieza.")
        return

    fecha_inicio = min(fechas)
    fecha_fin = max(fechas)
    print(f" -Limpiando datos entre {fecha_inicio} → {fecha_fin} ({origen})")

    try:
        tablas = [
            ("metricas_publicaciones_diarias", "fecha_descarga"),
            ("estadisticas_pagina_diaria", "fecha"),
            ("estadisticas_pagina_semanal", "fecha_corte_semana"),
            ("visitantes_pagina", "fecha_semana"),
        ]
        for tabla, campo in tablas:
            cur.execute(f"""
                DELETE FROM {tabla}
                WHERE plataforma='linkedin' AND {campo} BETWEEN %s AND %s;
            """, (fecha_inicio, fecha_fin))

        conn.commit()
        print(" -Limpieza completada correctamente.\n")

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] Limpieza {fecha_inicio} → {fecha_fin} ({origen})\n")

    except Exception as e:
        conn.rollback()
        print(f" Error al limpiar: {e}")


# Transformación XLS → CSV
def transformar_xls_a_csv():
    pythoncom.CoInitialize()

    archivos = glob.glob(os.path.join(EXPORTS_DIR, "*.xls"))
    if not archivos:
        print(" No hay archivos XLS en", EXPORTS_DIR)
        return

    def extraer_rango(nombre):
        match = re.search(r"(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})", nombre)
        if match:
            try:
                f1, f2 = match.groups()
                return (
                    datetime.strptime(f1, "%Y-%m-%d").date(),
                    datetime.strptime(f2, "%Y-%m-%d").date(),
                )
            except:
                pass
        return (datetime.min.date(), datetime.min.date())

    archivos_ordenados = sorted(
        archivos,
        key=lambda x: (extraer_rango(x)[1] - extraer_rango(x)[0]).days,
        reverse=True
    )

    procesados, omitidos = set(), []
    print(" -Transformando archivos XLS...")

    for file in archivos_ordenados:
        nombre = os.path.basename(file)
        tipo = (
            "Contenido" if "Contenido" in nombre else
            "Seguidores" if "Seguidores" in nombre else
            "Visitantes" if "Visitantes" in nombre else None
        )
        if not tipo or tipo in procesados:
            if tipo: omitidos.append(nombre)
            continue

        try:
            # Detectar si es binario antiguo
            with open(file, "rb") as f:
                es_binario = f.read(8).startswith(b"\xD0\xCF\x11\xE0")

            if es_binario:
                try:
                    excel = win32.gencache.EnsureDispatch("Excel.Application")
                    excel.Visible = False
                    excel.DisplayAlerts = False

                    wb = excel.Workbooks.Open(os.path.abspath(file))
                    temp_xlsx = os.path.join(tempfile.gettempdir(), nombre.replace(".xls", ".xlsx"))

                    # eliminar si ya existe
                    if os.path.exists(temp_xlsx):
                        os.remove(temp_xlsx)

                    wb.SaveAs(temp_xlsx, FileFormat=51)
                    wb.Close(SaveChanges=False)
                    excel.Quit()
                    file_to_read = temp_xlsx
                    print(f" * {nombre} convertido temporalmente → {temp_xlsx}")
                except Exception:
                    print(" No se pudo usar Excel COM, se leerá directo con pandas/xlrd...")
                    es_binario = False

            else:
                file_to_read = file

            # Cargar y exportar
            xls = pd.ExcelFile(file_to_read)
            if tipo == "Contenido":
                hojas = {
                    "Indicadores": "Contenido_Indicadores.csv",
                    "Todas las publicaciones": "Contenido_Publicaciones.csv"
                }
                for hoja, salida in hojas.items():
                    if hoja not in xls.sheet_names:
                        continue
                    df = pd.read_excel(xls, sheet_name=hoja, skiprows=1)
                    df.dropna(how="all", inplace=True)
                    df.to_csv(os.path.join(CLEAN_DIR, salida), index=False)
                    print(f" * {nombre} → {salida}")
            else:
                df = pd.read_excel(xls, sheet_name=0)
                df.dropna(how="all", inplace=True)
                salida = f"{tipo}.csv"
                df.to_csv(os.path.join(CLEAN_DIR, salida), index=False)
                print(f" * {nombre} → {salida}")

            procesados.add(tipo)

        except Exception as e:
            print(f" Error con {nombre}: {e}")

    if omitidos:
        print("\n -Archivos omitidos (ya cubiertos por un rango mayor):")
        for o in omitidos:
            print(f"   > {o}")
    print(" * Transformación completada.\n")


# Funciones auxiliares
def load_csv(path): return pd.read_csv(path)
def safe_get(row, col): return row[col] if col in row and pd.notna(row[col]) else None
def safe_parse_date(value):
    try: return pd.to_datetime(value, errors="coerce", dayfirst=False).date()
    except: return None


# Segmentación Segudires-Visitantes
def get_raw_file(pattern):
    files = glob.glob(os.path.join(EXPORTS_DIR, pattern))
    return files[0] if files else None


def ingest_segmentacion(file, tipo_entidad):
    try:
        # Intentar leer con pandas normalmente
        try:
            xls = pd.ExcelFile(file)
        except Exception as e:
            print(f" X xlrd no pudo leer {os.path.basename(file)}, convirtiendo con Excel COM...")

            try:
                pythoncom.CoInitialize()
                excel = win32.Dispatch("Excel.Application")
                excel.Visible = False
                excel.DisplayAlerts = False 

                wb = excel.Workbooks.Open(os.path.abspath(file))

                # Crear un archivo temporal único para evitar conflictos
                temp_xlsx = os.path.join(
                    tempfile.gettempdir(),
                    f"{os.path.basename(file).replace('.xls', '')}_{tipo_entidad}.xlsx"
                )

                # Si existe lo elimina
                if os.path.exists(temp_xlsx):
                    os.remove(temp_xlsx)

                wb.SaveAs(temp_xlsx, FileFormat=51)  # Guardar como .xlsx
                wb.Close(SaveChanges=False)
                excel.Quit()
                xls = pd.ExcelFile(temp_xlsx)
                print(f"* Archivo convertido temporalmente → {temp_xlsx}")

            except Exception as e2:
                print(f"❌ Error al convertir {file}: {e2}")
                return

        # Leer las hojas de segmentación
        for sheet in xls.sheet_names:
            if sheet.lower() in ["función laboral", "sector", "tamaño de la empresa", "ubicación", "nivel de responsabilidad"]:
                df = pd.read_excel(xls, sheet_name=sheet)
                df.dropna(how="all", inplace=True)
                for _, row in df.iterrows():
                    cur.execute("""
                        INSERT INTO segmentacion_pagina 
                            (pagina_id, plataforma, fecha, tipo_entidad, categoria, subcategoria, valor)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT ON CONSTRAINT uq_segmentacion DO UPDATE SET
                            valor = EXCLUDED.valor
                    """, (
                        PAGE_ID, "linkedin", date.today(),
                        tipo_entidad, sheet, safe_get(row, df.columns[0]), safe_get(row, df.columns[1])
                    ))
        print(f"- Segmentación cargada desde {file}")

    except Exception as e:
        print(f"X Error al procesar segmentación {file}: {e}")


# Insert extra (métricas)
def insert_extra(entidad_id, tipo_entidad, plataforma, fecha, row, columnas_principales=[], publicacion_id=None):
    if fecha is None: 
        fecha = date.today()

    # 🔹 Excluir solo las métricas principales (ya almacenadas en tablas base)
    METRICAS_EXCLUIR = {
        "Impresiones",
        "Clics",
        "Impresiones (totales)",
        "Clics (totales)",
        "Reacciones (total)",
        "Comentarios (totales)",
        "Veces compartido (total)",
        "Tasa de interacción (total)",
        "Visitantes únicos en total (total)",
        "Visualizaciones de la página en total (total)"
    }

    for col, val in row.items():
        if (
            col in columnas_principales 
            or col in METRICAS_EXCLUIR 
            or val is None 
            or str(val).strip() == ""
        ):
            continue

        valor_num, valor_texto = None, None
        try:
            valor_num = float(str(val).replace(",", "").replace("%", ""))
        except:
            valor_texto = str(val)

        cur.execute("""
            INSERT INTO metricas_extras (
                entidad_id, tipo_entidad, plataforma, fecha, 
                nombre_metrica, valor, valor_texto, publicacion_id, pagina_id
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT ON CONSTRAINT uq_metricas_extras DO UPDATE SET
                valor = EXCLUDED.valor,
                valor_texto = EXCLUDED.valor_texto
        """, (
            entidad_id, tipo_entidad, plataforma, fecha, col,
            valor_num, valor_texto, publicacion_id,
            PAGE_ID if publicacion_id is None else None
        ))


# Ingesta Contenido_Publicaciones
def ingest_publicaciones(path=f"{CLEAN_DIR}/Contenido_Publicaciones.csv"):
    print(" Ingestando publicaciones...")
    df = load_csv(path)
    for _, row in df.iterrows():
        pub_id = generar_pub_id(row)
        fecha_pub = safe_parse_date(row.get("Fecha de creación")) or date.today()
        cur.execute("""
            INSERT INTO publicaciones (publicacion_id, pagina_id, plataforma, fecha_hora_publicacion,
                                       texto_publicacion, formato, url_publicacion, fecha_descarga)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (publicacion_id) DO NOTHING
        """, (
            pub_id, PAGE_ID, "linkedin", fecha_pub,
            safe_get(row, "Título de la publicación"),
            safe_get(row, "Tipo de publicación"),
            safe_get(row, "Enlace de la publicación"),
            date.today()
        ))
        cur.execute("""
            INSERT INTO metricas_publicaciones_diarias (publicacion_id, pagina_id, plataforma, fecha_descarga,
                                                        impresiones, comentarios, compartidos, clics_enlace, ctr, total_reacciones)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT ON CONSTRAINT uq_metricas_publicacion_fecha DO UPDATE SET
                impresiones = EXCLUDED.impresiones,
                comentarios = EXCLUDED.comentarios,
                compartidos = EXCLUDED.comentarios,
                clics_enlace = EXCLUDED.clics_enlace,
                ctr = EXCLUDED.ctr,
                total_reacciones = EXCLUDED.total_reacciones
        """, (
            pub_id, PAGE_ID, "linkedin", date.today(),
            safe_get(row, "Impresiones"), safe_get(row, "Comentarios"),
            safe_get(row, "Veces compartido"), safe_get(row, "Clics"),
            safe_get(row, "CTR"), safe_get(row, "Reacciones")
        ))
        insert_extra(pub_id, "publicacion", "linkedin", fecha_pub, row,
                     ["Título de la publicación", "Tipo de publicación", "Enlace de la publicación", "Fecha de creación"],
                     publicacion_id=pub_id)
    print(" *Publicaciones insertadas correctamente\n")


# Ingesta Contenido_Indicadores
def ingest_indicadores(path=f"{CLEAN_DIR}/Contenido_Indicadores.csv"):
    print(" Ingestando indicadores...")
    df = load_csv(path)
    for _, row in df.iterrows():
        fecha = safe_parse_date(row.get("Fecha"))
        cur.execute("""
            INSERT INTO estadisticas_pagina_diaria (
                pagina_id, plataforma, fecha, impresiones_totales,
                clics_totales, reacciones_totales, comentarios_totales,
                compartidos_totales, tasa_interaccion, fecha_descarga
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (pagina_id, fecha) DO UPDATE SET
                impresiones_totales = EXCLUDED.impresiones_totales,
                clics_totales = EXCLUDED.clics_totales,
                reacciones_totales = EXCLUDED.reacciones_totales,
                comentarios_totales = EXCLUDED.comentarios_totales,
                compartidos_totales = EXCLUDED.compartidos_totales,
                tasa_interaccion = EXCLUDED.tasa_interaccion
        """, (
            PAGE_ID, "linkedin", fecha,
            safe_get(row, "Impresiones (totales)"),
            safe_get(row, "Clics (totales)"),
            safe_get(row, "Reacciones (total)"),
            safe_get(row, "Comentarios (totales)"),
            safe_get(row, "Veces compartido (total)"),
            safe_get(row, "Tasa de interacción (total)"),
            date.today()
        ))

        # 🔹 Ahora excluye las métricas principales de metricas_extras
        insert_extra(PAGE_ID, "indicadores", "linkedin", fecha, row, [
            "Fecha",
            "Impresiones", "Clics",
            "Impresiones (totales)", "Clics (totales)",
            "Reacciones (total)", "Comentarios (totales)",
            "Veces compartido (total)", "Tasa de interacción (total)",
            "Visitantes únicos en total (total)",
            "Visualizaciones de la página en total (total)"
        ])
    print(" *Indicadores cargados correctamente.\n")


# Ingesta Seguidores
def ingest_seguidores(path=f"{CLEAN_DIR}/Seguidores.csv"):
    print(" Ingestando seguidores...")
    df = load_csv(path)
    for _, row in df.iterrows():
        fecha = safe_parse_date(row.get("Fecha"))
        cur.execute("""
            INSERT INTO estadisticas_pagina_semanal (pagina_id, plataforma, fecha_corte_semana, total_seguidores)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT ON CONSTRAINT uq_pagina_semana DO UPDATE SET total_seguidores = EXCLUDED.total_seguidores
        """, (PAGE_ID, "linkedin", fecha, safe_get(row, "Total de seguidores")))
        insert_extra(PAGE_ID, "seguidores", "linkedin", fecha, row, ["Fecha", "Total de seguidores"])

    raw_file = get_raw_file("Seguidores*.xls")
    if raw_file:
        ingest_segmentacion(raw_file, "seguidores")
    print(" *Seguidores actualizados correctamente\n")


# Ingesta Visitantes
def ingest_visitantes(path=f"{CLEAN_DIR}/Visitantes.csv"):
    print(" Ingestando visitantes...")
    df = load_csv(path)
    for _, row in df.iterrows():
        fecha = safe_parse_date(row.get("Fecha"))
        cur.execute("""
            INSERT INTO visitantes_pagina (pagina_id, plataforma, fecha_semana, total_visitantes, visualizaciones)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT ON CONSTRAINT uq_visitantes_fecha DO UPDATE SET
                total_visitantes = EXCLUDED.total_visitantes,
                visualizaciones = EXCLUDED.visualizaciones
        """, (
            PAGE_ID, "linkedin", fecha,
            safe_get(row, "Visitantes únicos en total (total)"),
            safe_get(row, "Visualizaciones de la página en total (total)")
        ))
        insert_extra(PAGE_ID, "visitantes", "linkedin", fecha, row, ["Fecha"])

    raw_file = get_raw_file("Visitantes*.xls")
    if raw_file:
        ingest_segmentacion(raw_file, "visitantes")
    print(" *Visitantes cargados correctamente.\n")


# Main
def main():
    limpiar_rangos_previos()
    transformar_xls_a_csv()
    ingest_publicaciones()
    ingest_indicadores()
    ingest_seguidores()
    ingest_visitantes()
    conn.commit()
    cur.close()
    conn.close()
    print(" Ingesta completada con éxito")


if __name__ == "__main__":
    main()