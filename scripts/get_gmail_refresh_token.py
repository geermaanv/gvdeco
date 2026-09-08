"""
get_gmail_refresh_token.py
Correr UNA SOLA VEZ, en tu máquina (nunca en GitHub Actions), para obtener
el refresh token de Gmail que después se guarda como secret en GitHub.

Un service account no puede leer una casilla de Gmail personal sin
delegación de dominio de Google Workspace — por eso el pipeline usa OAuth
de usuario con un refresh token de larga duración en su lugar.

Requiere: pip install google-auth-oauthlib

Antes de correr:
1. Google Cloud Console → Credentials → Create credentials → OAuth client ID
   → tipo "Desktop app". Descargá el JSON y guardalo como client_secret.json
   en esta misma carpeta (no lo commitees).
2. En OAuth consent screen agregá el scope de Gmail y, si la app queda en
   modo "Testing", agregá tu propia cuenta como test user.
"""

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def main():
    flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    creds = flow.run_local_server(port=0)

    print("\nGuardá estos 3 valores como secrets en GitHub (Settings → Secrets → Actions):\n")
    print(f"GMAIL_CLIENT_ID={creds.client_id}")
    print(f"GMAIL_CLIENT_SECRET={creds.client_secret}")
    print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
