"""
Hoval Connect Setup Tool
========================
Sicherheitskonzept:
- Email/Passwort werden NUR im RAM gehalten, nie auf Disk geschrieben
- Übertragung nur via HTTPS an SAP IAS (Hoval)
- Browser läuft headless (unsichtbar)
- Credentials werden nach Login sofort aus RAM gelöscht
- Tokens werden nur in Zwischenablage kopiert, nicht gespeichert
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import base64
import hashlib
import os
import sys
import gc
import requests
from urllib.parse import urlencode, parse_qs

CLIENT_ID    = "991b54b2-7e67-47ef-81fe-572e21c59899"
REDIRECT_URI = "com.hoval.connect2://redirect"
SCOPE        = "openid offline_access"
AUTH_URL     = "https://akwc5scsc.accounts.ondemand.com/oauth2/authorize"
TOKEN_URL    = "https://akwc5scsc.accounts.ondemand.com/oauth2/token"
APP_HEADERS  = {
    "User-Agent": "HovalConnect/6022 CFNetwork/3860.400.51 Darwin/25.3.0",
    "Accept": "application/json",
}


def pkce():
    v = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    c = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    return v, c


def login_and_get_tokens(username: str, password: str, status_callback) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright nicht installiert.\n"
            "Bitte install.bat ausführen."
        )

    verifier, challenge = pkce()
    params = urlencode({
        "response_type": "code", "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI, "scope": SCOPE,
        "state": "state", "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    start_url = f"{AUTH_URL}?{params}"
    code = None

    status_callback("Browser startet im Hintergrund...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"
        )
        page = context.new_page()

        def handle_request(request):
            nonlocal code
            url = request.url
            if url.startswith("com.hoval.connect2://") and "code=" in url:
                qs = url.split("?", 1)[-1] if "?" in url else ""
                codes = parse_qs(qs).get("code", [])
                if codes:
                    code = codes[0]

        page.on("request", handle_request)

        status_callback("Verbinde mit Hoval (verschlüsselt)...")
        try:
            page.goto(start_url, wait_until="networkidle", timeout=15000)
        except Exception:
            pass

        status_callback("Anmelden...")
        try:
            page.wait_for_selector('input[name="j_username"]', timeout=10000)
            page.fill('input[name="j_username"]', username)
            page.fill('input[name="j_password"]', password)
        except Exception:
            try:
                page.fill('input[type="email"]', username)
                page.fill('input[type="password"]', password)
            except Exception as e:
                context.close()
                browser.close()
                raise RuntimeError(f"Login-Formular nicht gefunden: {e}")

        try:
            page.click('button[type="submit"]')
        except Exception:
            page.keyboard.press("Enter")

        status_callback("Warte auf Bestätigung von Hoval...")
        try:
            page.wait_for_function(
                "() => window.location.href.startsWith('com.hoval')",
                timeout=10000
            )
        except Exception:
            pass

        if not code:
            current = page.url
            if "code=" in current:
                qs = current.split("?", 1)[-1] if "?" in current else ""
                codes = parse_qs(qs).get("code", [])
                if codes:
                    code = codes[0]

        context.close()
        browser.close()

    if not code:
        raise RuntimeError(
            "Anmeldung fehlgeschlagen.\n\n"
            "Mögliche Ursachen:\n"
            "• Falsches Passwort\n"
            "• 2-Faktor-Authentifizierung aktiv\n"
            "• Keine Internetverbindung"
        )

    status_callback("Tokens werden abgerufen...")

    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
        headers={**APP_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )

    if r.status_code != 200:
        raise RuntimeError(f"Token-Abruf fehlgeschlagen ({r.status_code})")

    return r.json()


class SetupApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hoval Connect – Einrichtung")
        self.root.resizable(False, False)

        w, h = 480, 400
        root.update_idletasks()
        x = (root.winfo_screenwidth() // 2) - (w // 2)
        y = (root.winfo_screenheight() // 2) - (h // 2)
        root.geometry(f"{w}x{h}+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#1a73e8", height=65)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="🔥  Hoval Connect – Einrichtung",
            font=("Segoe UI", 13, "bold"), bg="#1a73e8", fg="white"
        ).pack(expand=True)

        main = tk.Frame(self.root, padx=35, pady=25)
        main.pack(fill="both", expand=True)

        tk.Label(
            main, text="Hoval Zugangsdaten eingeben",
            font=("Segoe UI", 10, "bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 15))

        tk.Label(main, text="Email:", font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w", pady=8)
        self.email_var = tk.StringVar()
        ttk.Entry(main, textvariable=self.email_var, width=34).grid(row=1, column=1, sticky="ew", pady=8)

        tk.Label(main, text="Passwort:", font=("Segoe UI", 10)).grid(row=2, column=0, sticky="w", pady=8)
        self.pw_var = tk.StringVar()
        ttk.Entry(main, textvariable=self.pw_var, show="•", width=34).grid(row=2, column=1, sticky="ew", pady=8)

        # Status
        self.status_var = tk.StringVar()
        tk.Label(
            main, textvariable=self.status_var,
            font=("Segoe UI", 9), fg="#555", wraplength=400
        ).grid(row=3, column=0, columnspan=2, pady=(20, 0))

        self.progress = ttk.Progressbar(main, mode="indeterminate", length=400)
        self.progress.grid(row=4, column=0, columnspan=2, pady=(8, 0))

        self.btn = ttk.Button(
            main, text="🔑   Tokens holen",
            command=self._start
        )
        self.btn.grid(row=5, column=0, columnspan=2, pady=(20, 0), ipadx=20, ipady=7)

        tk.Label(
            main,
            text="🔒 Zugangsdaten werden nur verschlüsselt an Hoval übertragen und nie gespeichert.",
            font=("Segoe UI", 8), fg="#999", wraplength=410
        ).grid(row=6, column=0, columnspan=2, pady=(15, 0))

        main.columnconfigure(1, weight=1)

    def _set_status(self, msg: str):
        self.status_var.set(msg)
        self.root.update_idletasks()

    def _start(self):
        email    = self.email_var.get().strip()
        password = self.pw_var.get()

        if not email or "@" not in email:
            messagebox.showerror("Fehler", "Bitte eine gültige Email-Adresse eingeben.")
            return
        if not password:
            messagebox.showerror("Fehler", "Bitte das Passwort eingeben.")
            return

        self.btn.config(state="disabled")
        self.progress.start(10)

        def run():
            try:
                token_data = login_and_get_tokens(email, password, self._set_status)
                access_token  = token_data["access_token"]
                refresh_token = token_data["refresh_token"]

                # Passwort sofort löschen
                self.pw_var.set("")
                gc.collect()

                # Tokens in Zwischenablage
                self.root.clipboard_clear()
                self.root.clipboard_append(
                    f"{access_token}\n{refresh_token}"
                )

                self.progress.stop()
                self.btn.config(state="normal")
                self._set_status("✅ Erfolgreich! Tokens bereit.")

                # Ergebnis-Fenster
                self._show_result(access_token, refresh_token)

                # Tokens aus RAM löschen
                del access_token, refresh_token, token_data
                gc.collect()

            except Exception as e:
                self.progress.stop()
                self.btn.config(state="normal")
                self._set_status(f"❌ {str(e)[:80]}")
                messagebox.showerror("Fehler", str(e))

        threading.Thread(target=run, daemon=True).start()

    def _show_result(self, access_token: str, refresh_token: str):
        """Zeigt Tokens übersichtlich an mit Copy-Buttons."""
        win = tk.Toplevel(self.root)
        win.title("Tokens – In Home Assistant einfügen")
        win.resizable(False, False)
        win.grab_set()

        w, h = 560, 420
        x = (win.winfo_screenwidth() // 2) - (w // 2)
        y = (win.winfo_screenheight() // 2) - (h // 2)
        win.geometry(f"{w}x{h}+{x}+{y}")

        # Header
        hdr = tk.Frame(win, bg="#27ae60", height=55)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="✅  Login erfolgreich – Tokens bereit",
                 font=("Segoe UI", 12, "bold"), bg="#27ae60", fg="white").pack(expand=True)

        f = tk.Frame(win, padx=25, pady=15)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="In Home Assistant: Einstellungen → Integrationen → Hoval Connect → Tokens einfügen",
                 font=("Segoe UI", 9), fg="#555", wraplength=500).pack(pady=(0, 15))

        # Access Token
        tk.Label(f, text="Access Token:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        at_frame = tk.Frame(f)
        at_frame.pack(fill="x", pady=(3, 10))
        at_text = tk.Text(at_frame, height=3, font=("Courier", 8), wrap="char")
        at_text.insert("1.0", access_token)
        at_text.config(state="disabled")
        at_text.pack(side="left", fill="x", expand=True)
        ttk.Button(at_frame, text="📋 Kopieren",
                   command=lambda: self._copy(access_token)).pack(side="right", padx=(8,0))

        # Refresh Token
        tk.Label(f, text="Refresh Token:", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        rt_frame = tk.Frame(f)
        rt_frame.pack(fill="x", pady=(3, 10))
        rt_text = tk.Text(rt_frame, height=2, font=("Courier", 8), wrap="char")
        rt_text.insert("1.0", refresh_token)
        rt_text.config(state="disabled")
        rt_text.pack(side="left", fill="x", expand=True)
        ttk.Button(rt_frame, text="📋 Kopieren",
                   command=lambda: self._copy(refresh_token)).pack(side="right", padx=(8,0))

        tk.Label(f, text="💡 Tipp: Tokens werden automatisch erneuert. Diese Einrichtung ist einmalig.",
                 font=("Segoe UI", 8), fg="#888", wraplength=500).pack(pady=(5,0))

        ttk.Button(f, text="Schließen", command=win.destroy).pack(pady=(15,0))

    def _copy(self, text: str):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)


if __name__ == "__main__":
    try:
        import playwright
    except ImportError:
        import subprocess
        print("Installiere Playwright (einmalig)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright", "-q"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"], check=True)

    root = tk.Tk()
    SetupApp(root)
    root.mainloop()
