#  DATAX – Ingesta de LinkedIn con Playwright + PostgreSQL

Automatización desarrollada para **descargar, limpiar e ingestar datos de LinkedIn** en PostgreSQL.
El sistema utiliza **Python + Playwright** para la extracción automática y **Pandas + psycopg2** para la transformación y carga de datos.

---

## Requisitos

- Python 3.10 o superior  
- PostgreSQL (con URL configurada en `.env`)  
- Entorno virtual activo  
ejemplo de env:
   PG_URL=postgresql://postgres:postgres@localhost:5432/Base_De_Datos
   LI_PAGE_ID= ID_Linkedin


## Estructura del Proyecto_Playwright/
│
├── linkedin.py               # Descarga automática desde LinkedIn
├── li_ingest_csv.py          # Limpieza y carga de datos
├── dependencia.txt           # Librerías necesarias
├── .env                      # Variables de entorno
├── linkedin_session.json     # Sesión Playwright (login automático)
├── linkedin_exports/         # Descargas brutas desde LinkedIn
├── linkedin_clean/           # Archivos CSV limpios y listos para ingesta
└── logs/                     # Registros de ejecución

## Notas 
-Los IDs de publicaciones se generan con hash SHA1 para evitar duplicados.
-Los archivos .xls se transforman automáticamente en .csv con codificación detectada.
-Los delimitadores se reconocen dinámicamente (;, ,, \t).
-El proceso es compatible con múltiples rangos de fechas y pestañas.