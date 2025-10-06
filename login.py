# import os
# import os
# from playwright.sync_api import sync_playwright

# SESSIONS = {
#     "facebook": {
#         "url": "https://www.facebook.com/login",
#         "file": "fb_session.json"
#     },
#     "instagram": {
#         "url": "https://www.instagram.com/?flo=true",
#         "file": "ig_session.json"
#     },
#     "tiktok": {
#         "url": "https://www.tiktok.com/login/phone-or-email/email",
#         "file": "tiktok_session.json"
#     },
#     "linkedin": {
#         "url": "https://www.linkedin.com/login",
#         "file": "linkedin_session.json"
#     }
# }

# def get_context(playwright, platform: str):
#     """
#     Devuelve un browser, context y page logueados en la plataforma indicada.
#     - platform: "facebook", "instagram", "tiktok", "linkedin"
#     """
#     if platform not in SESSIONS:
#         raise ValueError(f"Plataforma no soportada: {platform}")

#     session_info = SESSIONS[platform]
#     session_file = session_info["file"]
#     url = session_info["url"]

#     browser = playwright.chromium.launch(headless=False)

#     if not os.path.exists(session_file):
#         # Primera vez: login manual
#         context = browser.new_context()
#         page = context.new_page()
#         page.goto(url)

#         print(f"Inicia sesión manualmente en {platform}")
#         page.wait_for_timeout(120000) 

#         context.storage_state(path=session_file)
#         print(f"Sesión de {platform} guardada en {session_file}")
#     else:
#         context = browser.new_context(storage_state=session_file)
#         page = context.new_page()
#         page.goto(url.replace("/login", ""))  
#         print(f"Sesión de {platform} cargada desde {session_file}")

#     return browser, context, page



import os
import os
from playwright.sync_api import sync_playwright

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
