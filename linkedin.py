import os
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright
from login import get_context

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


