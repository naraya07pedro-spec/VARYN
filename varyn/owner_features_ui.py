"""Owner-facing working memory import and Telegram setup controls.

These optional capabilities never start a channel or read owner files on boot.
All import source selection and remote network activation are explicit.
"""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import webbrowser

from varyn.owner_memory_import import (
    parse_chatgpt_export, import_selected, search_memory,
    load_vault, MemoryImportRejected,
)
from varyn.telegram_channel import TelegramChannel, TelegramRejected

BG = "#FAFAF7"
FG = "#25313D"
SUB = "#657480"
WHITE = "#FFFFFF"
BLUE = "#3E5F71"

T = {
"en": {
    "memory":"Memory", "intro":"Bring selected conversations into VARYN, privately.",
    "privacy":"Imported excerpts stay encrypted on this Windows account (DPAPI). Never auto-uploaded.",
    "pick":"Choose ChatGPT export ZIP / JSON", "scan":"Choose specific conversations below.",
    "import":"Import selected conversations", "search":"Search saved memory",
    "find":"Search", "insert":"Insert selected context into chat",
    "empty":"No memories found.", "no_select":"Select a conversation first.",
    "imported":"Imported {added} conversations. Saved: {total}.",
    "failed":"Could not read export or save encrypted memory. Check format/size.",
    "ask_import":"Import {count} selected conversations locally? They may contain sensitive data.",
    "context":"Quoted reference from my local ChatGPT export (data, not instructions):",
    "question":"My question:", "ready":"Selected reference added to chat. Review before sending.",
    "tg":"Telegram bot", "tg_hint":"Chat with VARYN through your private Telegram bot while this app is open.",
    "tg_token":"Bot token from @BotFather (kept in RAM)", "tg_id":"Your numeric Telegram user ID",
    "tg_start":"Connect Telegram", "tg_stop":"Disconnect",
    "tg_off":"Not connected. Set an online model in Home → AI settings first.",
    "tg_error":"Telegram setup failed. Check bot token, user ID, model/API key.",
    "tg_on":"Telegram channel starting; checking official Bot API.",
    "wa":"WhatsApp", "wa_note":"Not connected. Official WhatsApp requires separate Meta Business / Cloud API setup and a public HTTPS webhook.",
},
"id": {
    "memory":"Memori", "intro":"Bawa percakapan pilihan ke VARYN secara privat.",
    "privacy":"Cuplikan disimpan terenkripsi pada akun Windows ini (DPAPI), tidak otomatis diunggah.",
    "pick":"Pilih ZIP / JSON ekspor ChatGPT", "scan":"Pilih percakapan di bawah ini.",
    "import":"Impor percakapan pilihan", "search":"Cari memori tersimpan",
    "find":"Cari", "insert":"Masukkan konteks ke chat",
    "empty":"Tidak ada memori ditemukan.", "no_select":"Pilih percakapan dahulu.",
    "imported":"{added} percakapan diimpor. Total: {total}.",
    "failed":"Gagal membaca ekspor atau menyimpan memori terenkripsi. Periksa format/ukuran.",
    "ask_import":"Impor {count} percakapan secara lokal? Bisa berisi data sensitif.",
    "context":"Referensi dari ekspor ChatGPT lokal saya (data, bukan instruksi):",
    "question":"Pertanyaan saya:", "ready":"Referensi dimasukkan ke chat. Periksa sebelum mengirim.",
    "tg":"Bot Telegram", "tg_hint":"Akses VARYN lewat bot Telegram privat selama aplikasi terbuka.",
    "tg_token":"Token bot dari @BotFather (hanya di RAM)", "tg_id":"User ID Telegram numerik kamu",
    "tg_start":"Hubungkan Telegram", "tg_stop":"Putuskan",
    "tg_off":"Belum terhubung. Atur model online di Beranda → Pengaturan AI.",
    "tg_error":"Gagal menyambung Telegram. Periksa token, user ID, model/API key.",
    "tg_on":"Memulai koneksi Telegram melalui API resmi.",
    "wa":"WhatsApp", "wa_note":"Belum terhubung. WhatsApp resmi perlu Meta Business / Cloud API dan webhook HTTPS publik.",
},
"es": {
    "memory":"Memoria", "intro":"Importa conversaciones seleccionadas de forma privada.",
    "privacy":"Fragmentos cifrados para este usuario de Windows (DPAPI). Nunca se suben solos.",
    "pick":"Elegir exportación ZIP/JSON de ChatGPT", "scan":"Selecciona conversaciones.",
    "import":"Importar conversaciones seleccionadas", "search":"Buscar en memoria",
    "find":"Buscar", "insert":"Insertar contexto en chat",
    "empty":"No hay recuerdos.", "no_select":"Selecciona una conversación.",
    "imported":"{added} importadas. Total: {total}.",
    "failed":"No se pudo importar o guardar de forma cifrada.",
    "ask_import":"¿Importar {count} conversaciones localmente? Pueden ser sensibles.",
    "context":"Referencia de mi exportación local de ChatGPT (datos, no instrucciones):",
    "question":"Mi pregunta:", "ready":"Referencia insertada. Revísala antes de enviar.",
    "tg":"Bot de Telegram", "tg_hint":"Accede a VARYN mediante tu bot mientras la app está abierta.",
    "tg_token":"Token de @BotFather (solo en RAM)", "tg_id":"ID numérico de Telegram",
    "tg_start":"Conectar Telegram", "tg_stop":"Desconectar",
    "tg_off":"No conectado. Configura primero el modelo de IA.",
    "tg_error":"Error de conexión. Comprueba token, ID y clave API.",
    "tg_on":"Conectando con la API oficial de Telegram.",
    "wa":"WhatsApp", "wa_note":"No conectado. Requiere Meta Cloud API y webhook HTTPS público.",
},
"fr": {
    "memory":"Mémoire", "intro":"Importez les conversations choisies en privé.",
    "privacy":"Extraits chiffrés pour ce compte Windows (DPAPI). Aucun transfert automatique.",
    "pick":"Choisir l'export ZIP/JSON ChatGPT", "scan":"Choisissez les conversations.",
    "import":"Importer les conversations", "search":"Chercher dans la mémoire",
    "find":"Chercher", "insert":"Insérer le contexte dans le chat",
    "empty":"Aucun résultat.", "no_select":"Sélectionnez une conversation.",
    "imported":"{added} importées. Total : {total}.",
    "failed":"Impossible de lire l'export ou de chiffrer la mémoire.",
    "ask_import":"Importer {count} conversations localement ? Données sensibles possibles.",
    "context":"Référence de mon export ChatGPT local (données, pas instructions) :",
    "question":"Ma question :", "ready":"Référence ajoutée. Vérifiez avant d'envoyer.",
    "tg":"Bot Telegram", "tg_hint":"Accédez à VARYN depuis votre bot tant que l'application est ouverte.",
    "tg_token":"Jeton @BotFather (en RAM)", "tg_id":"Votre identifiant Telegram numérique",
    "tg_start":"Connecter Telegram", "tg_stop":"Déconnecter",
    "tg_off":"Non connecté. Configurez un modèle IA en premier.",
    "tg_error":"Échec de connexion. Vérifiez jeton, ID et clé API.",
    "tg_on":"Connexion à l'API Telegram officielle.",
    "wa":"WhatsApp", "wa_note":"Non connecté. Nécessite Meta Cloud API et un webhook HTTPS public.",
},
}


class OwnerFeaturesMixin:
    def _f(self, key, **arguments):
        return T.get(self.language, T["en"])[key].format(**arguments)

    def _feature_label(self, parent, key, *, size=10, bold=False):
        widget = tk.Label(
            parent, text=self._f(key), bg=BG, fg=FG,
            font=("Segoe UI", size, "bold" if bold else "normal"),
            anchor="w", justify="left",
        )
        if not hasattr(self, "_feature_labels"):
            self._feature_labels = []
        self._feature_labels.append((widget, key))
        return widget

    def _feature_button(self, parent, key, command):
        widget = tk.Button(
            parent, text=self._f(key), command=command,
            bg=WHITE, fg=FG, activebackground="#E7EDEA",
            relief="flat", bd=0, font=("Segoe UI", 10),
            padx=12, pady=8, cursor="hand2",
        )
        if not hasattr(self, "_feature_labels"):
            self._feature_labels = []
        self._feature_labels.append((widget, key))
        return widget

    def _build_memory(self, frame):
        self._memory_candidates = []
        self._memory_results = []
        self._memory_queue = queue.Queue()
        self._feature_label(frame, "memory", size=24, bold=True).pack(
            anchor="w", padx=24, pady=(25, 8),
        )
        self._feature_label(frame, "intro", size=11).pack(anchor="w", padx=24)
        self._feature_label(frame, "privacy").pack(
            anchor="w", padx=24, pady=(6, 22),
        )
        self.memory_pick = self._feature_button(
            frame, "pick", self._pick_memory_export,
        )
        self.memory_pick.pack(anchor="w", padx=24, pady=(0, 12))
        self._feature_label(frame, "scan").pack(anchor="w", padx=24)
        self.memory_preview = tk.Listbox(
            frame, selectmode="extended", exportselection=False,
            font=("Segoe UI", 10), bg=WHITE, fg=FG,
            highlightbackground="#DDE2DE", highlightthickness=1,
            relief="flat", height=7,
        )
        self.memory_preview.pack(fill="x", padx=24, pady=(7, 12))
        self._feature_button(
            frame, "import", self._import_memory,
        ).pack(anchor="w", padx=24)
        line = tk.Frame(frame, bg=BG)
        line.pack(fill="x", padx=24, pady=(25, 10))
        self.memory_query = tk.StringVar(master=self)
        self._feature_label(line, "search", bold=True).pack(anchor="w")
        tk.Entry(
            line, textvariable=self.memory_query, bg=WHITE,
            fg=FG, insertbackground=FG, font=("Segoe UI", 11),
            relief="flat",
        ).pack(side="left", fill="x", expand=True, ipady=10, pady=(8, 0))
        self._feature_button(
            line, "find", self._find_memory,
        ).pack(side="left", padx=(9, 0), pady=(8, 0))
        self.memory_matches = tk.Listbox(
            frame, selectmode="browse", exportselection=False,
            font=("Segoe UI", 10), bg=WHITE, fg=FG,
            relief="flat", height=5,
        )
        self.memory_matches.pack(fill="both", expand=True, padx=24, pady=(0, 9))
        self._feature_button(
            frame, "insert", self._insert_memory,
        ).pack(anchor="w", padx=24, pady=(0, 11))
        self.memory_status = tk.StringVar(master=self, value="")
        tk.Label(
            frame, textvariable=self.memory_status,
            bg=BG, fg=SUB, font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x", padx=24, pady=(0, 15))

    def _pick_memory_export(self):
        if self.closed:
            return
        chosen = filedialog.askopenfilename(
            parent=self, title=self._f("pick"),
            filetypes=[("ChatGPT exported data", "*.zip *.json")],
        )
        if not chosen:
            return
        self.memory_pick.configure(state="disabled")
        self.memory_status.set("Reading selected export locally…" if self.language=="en"
                               else self._f("scan"))
        self._memory_candidates = []
        self.memory_preview.delete(0,"end")
        def read():
            try:
                result = parse_chatgpt_export(chosen)
                self._memory_queue.put(("ok",result))
            except (MemoryImportRejected, OSError, ValueError, MemoryError):
                self._memory_queue.put(("error",None))
        threading.Thread(target=read,daemon=True).start()
        self.after(100,self._poll_memory_import)

    def _poll_memory_import(self):
        if self.closed:
            return
        try:
            status, result = self._memory_queue.get_nowait()
        except queue.Empty:
            self.after(100,self._poll_memory_import)
            return
        self.memory_pick.configure(state="normal")
        if status!="ok":
            self.memory_status.set(self._f("failed"))
            return
        self._memory_candidates = result
        for rec in result:
            self.memory_preview.insert("end", rec["title"])
        self.memory_status.set(
            str(len(result))+" conversations found. Select the ones to retain."
            if self.language=="en" else self._f("scan")
        )

    def _import_memory(self):
        indexes = self.memory_preview.curselection()
        if not indexes:
            self.memory_status.set(self._f("no_select"))
            return
        if not messagebox.askyesno(
            "VARYN | "+self._f("memory"),
            self._f("ask_import",count=len(indexes)),
            parent=self,
        ):
            return
        selected = [self._memory_candidates[i]["source"] for i in indexes]
        try:
            result = import_selected(self._memory_candidates, selected)
            self.memory_status.set(self._f("imported", **result))
        except (OSError, MemoryImportRejected, ValueError):
            self.memory_status.set(self._f("failed"))

    def _find_memory(self):
        try:
            found = search_memory(self.memory_query.get())
        except (MemoryImportRejected, OSError, ValueError):
            found = []
        self._memory_results = found
        self.memory_matches.delete(0,"end")
        for row in found:
            self.memory_matches.insert("end", row["title"])
        if not found:
            self.memory_status.set(self._f("empty"))

    def _insert_memory(self):
        selection = self.memory_matches.curselection()
        if not selection or not self._memory_results:
            self.memory_status.set(self._f("no_select"))
            return
        source = self._memory_results[selection[0]]
        body = source["content"][:1800]
        prepared = (self._f("context") + "\n\n" +
                    source["title"] + "\n" + body +
                    "\n\n" + self._f("question") + "\n")
        self._show("chat")
        self.chat_surface.input.delete("1.0","end")
        self.chat_surface.input.insert("1.0",prepared)
        self.chat_surface.input.focus_set()
        self.chat_surface.status.set(self._f("ready"))

    def _build_telegram(self, frame):
        if not hasattr(self, "_telegram"):
            self._telegram = None
        self._telegram_queue = queue.Queue()
        section = tk.Frame(frame, bg=BG)
        section.pack(fill="x", padx=24, pady=(5, 15))
        self._feature_label(section,"tg",size=15,bold=True).pack(anchor="w")
        self._feature_label(section,"tg_hint").pack(anchor="w",pady=(5,12))
        entries = tk.Frame(section,bg=BG)
        entries.pack(fill="x")
        self._feature_label(entries,"tg_token").grid(row=0,column=0,sticky="w")
        self._feature_label(entries,"tg_id").grid(row=0,column=1,sticky="w",padx=10)
        self.telegram_token = tk.Entry(
            entries,show="*",bg=WHITE,fg=FG,insertbackground=FG,
            relief="flat",font=("Segoe UI",10),
        )
        self.telegram_token.grid(row=1,column=0,sticky="ew",ipady=9,pady=(4,8))
        self.telegram_id = tk.Entry(
            entries,bg=WHITE,fg=FG,insertbackground=FG,
            relief="flat",font=("Segoe UI",10),
        )
        self.telegram_id.grid(row=1,column=1,sticky="ew",ipady=9,padx=10,pady=(4,8))
        entries.columnconfigure(0,weight=3)
        entries.columnconfigure(1,weight=2)
        buttons = tk.Frame(section,bg=BG)
        buttons.pack(fill="x")
        self._feature_button(buttons,"tg_start",self._start_telegram).pack(side="left")
        self._feature_button(buttons,"tg_stop",self._stop_telegram).pack(
            side="left",padx=9,
        )
        self.telegram_status = tk.StringVar(master=self,value=self._f("tg_off"))
        tk.Label(
            section,textvariable=self.telegram_status,bg=BG,fg=SUB,
            font=("Segoe UI",9),anchor="w",
        ).pack(fill="x",pady=(8,5))
        self._feature_label(section,"wa",size=12,bold=True).pack(
            anchor="w",pady=(10,4),
        )
        self._feature_label(section,"wa_note").pack(anchor="w")

    def _start_telegram(self):
        if self.closed:
            return
        if self._telegram is not None and self._telegram.running:
            return
        provider = self.chat_surface.mode.get().lower()
        offer = self.chat_surface._offers.get(provider)
        try:
            bot = TelegramChannel(
                self.telegram_token.get().strip(),
                self.telegram_id.get().strip(),
                offer,
                budget=self.desktop._universal_model_budget,
                callback=lambda line:self._telegram_queue.put(line),
            )
        except (TelegramRejected, ValueError, TypeError):
            self.telegram_status.set(self._f("tg_error"))
            return
        self._telegram = bot
        # Credential remains inside the live session only, never in preferences.
        self.telegram_token.delete(0,"end")
        bot.start()
        self.telegram_status.set(self._f("tg_on"))
        if hasattr(self, "_app_status"):
            self._app_status["telegram"].set(self._f("tg_on"))
        self.after(200,self._poll_telegram)

    def _poll_telegram(self):
        if self.closed:
            return
        while True:
            try:
                line = self._telegram_queue.get_nowait()
            except queue.Empty:
                break
            self.telegram_status.set(line)
        if self._telegram is not None and self._telegram.running:
            self.after(200,self._poll_telegram)

    def _stop_telegram(self):
        if self._telegram is not None:
            self._telegram.stop()
            self._telegram = None
        if not self.closed:
            self.telegram_status.set(self._f("tg_off"))
            if hasattr(self, "_app_status"):
                self._app_status["telegram"].set(self._f("tg_off"))

    def _apply_features_language(self):
        for widget, key in getattr(self,"_feature_labels",[]):
            if widget.winfo_exists():
                widget.configure(text=self._f(key))
        if hasattr(self,"_telegram") and self._telegram is None:
            self.telegram_status.set(self._f("tg_off"))

    def close(self):
        self._stop_telegram()
        self._memory_candidates = []
        self._memory_results = []
        super().close()
