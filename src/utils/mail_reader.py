"""
utils/mail_reader.py
Lee el correo del IMSS automáticamente para extraer:
  - Link de verificación / token
  - NSS contenido en el correo

Compatible con Gmail, Outlook y cualquier servidor IMAP estándar.

CONFIGURACIÓN GMAIL:
  1. Ve a myaccount.google.com -> Seguridad -> Verificación en dos pasos (activa)
  2. Busca "Contraseñas de aplicaciones"
  3. Genera una para "Correo / Windows"
  4. Usa esa contraseña de 16 chars en IMAP_PASSWORD
"""

import os
import re
import time
import email
from imapclient import IMAPClient


class MailReaderError(Exception):
    pass


class MailReader:
    IMSS_SENDERS = [
        "noreply@imss.gob.mx",
        "serviciosdigitales@imss.gob.mx",
        "no-reply@imss.gob.mx",
    ]

    def __init__(self):
        self.server   = os.getenv("IMAP_SERVER", "imap.gmail.com")
        self.port     = int(os.getenv("IMAP_PORT", "993"))
        self.email    = os.getenv("IMAP_EMAIL", "")
        self.password = os.getenv("IMAP_PASSWORD", "")

        if not self.email or not self.password:
            raise MailReaderError(
                "IMAP_EMAIL e IMAP_PASSWORD no configurados en config.env"
            )

    def wait_for_imss_email(
        self, subject_hint: str = "NSS", max_wait_sec: int = 180, interval: int = 8
    ) -> dict:
        """
        Espera un correo del IMSS y extrae el contenido relevante.
        Retorna dict con: subject, body, link, nss (si lo detecta)
        """
        print(f"  [mail] Esperando correo IMSS (máx {max_wait_sec}s)...")
        elapsed = 0

        with IMAPClient(self.server, port=self.port, ssl=True) as client:
            client.login(self.email, self.password)
            client.select_folder("INBOX")

            start_uid = self._get_latest_uid(client)

            while elapsed < max_wait_sec:
                time.sleep(interval)
                elapsed += interval

                messages = client.search(["UNSEEN", "FROM", "imss.gob.mx"])
                new_msgs  = [uid for uid in messages if uid > start_uid]

                if new_msgs:
                    uid = max(new_msgs)
                    raw = client.fetch([uid], ["RFC822"])[uid][b"RFC822"]
                    msg = email.message_from_bytes(raw)
                    result = self._parse_message(msg)
                    print(f"  [mail] Correo recibido en {elapsed}s [OK]")
                    client.set_flags([uid], [b"\\Seen"])
                    return result

                print(f"  [mail] Sin correo aún... ({elapsed}s)")

        raise MailReaderError(
            f"No llegó correo del IMSS en {max_wait_sec}s. "
            "Verifica que el correo sea correcto y revisa spam."
        )

    def _get_latest_uid(self, client) -> int:
        """Obtiene el UID más reciente para detectar solo correos nuevos."""
        all_msgs = client.search(["ALL"])
        return max(all_msgs) if all_msgs else 0

    def _parse_message(self, msg) -> dict:
        """Extrae body, links y NSS del correo."""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/plain":
                    body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    break
                elif ctype == "text/html" and not body:
                    html = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    body = re.sub(r"<[^>]+>", " ", html)
        else:
            body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")

        # Buscar NSS (11 dígitos)
        nss_match = re.search(r"\b(\d{11})\b", body)
        nss = nss_match.group(1) if nss_match else None

        # Buscar links de verificación
        links = re.findall(r"https?://[^\s\"<>]+", body)
        verification_link = next(
            (l for l in links if "verif" in l.lower() or "confirm" in l.lower() or "token" in l.lower()),
            links[0] if links else None,
        )

        return {
            "subject":           msg.get("Subject", ""),
            "from":              msg.get("From", ""),
            "body":              body.strip(),
            "nss":               nss,
            "verification_link": verification_link,
            "all_links":         links,
        }
