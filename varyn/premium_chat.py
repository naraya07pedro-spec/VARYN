"""Consumer-first VARYN conversation: reference-style home, real chat on send.

No external request is made by painting the home. Existing ChatSurface owns
all model/provider, billing, network, human-approval and error boundaries.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from varyn.simple_chat import ChatSurface
from varyn.twilight_banner import TwilightBanner


BG = "#161b32"
CARD = "#272b48"
BORDER = "#494565"
FG = "#f9f6ff"
MUTED = "#b9b9cf"
PURPLE = "#9565f1"


class QuickCard(tk.Canvas):
    """Clickable, keyboard-accessible navigation card with round corners."""

    def __init__(self, parent, title, subtitle, icon, command):
        super().__init__(
            parent, height=143, bg=BG, bd=0, highlightthickness=0,
            takefocus=1, cursor="hand2",
        )
        self.title_text = title
        self.subtitle = subtitle
        self.symbol = icon
        self.command = command
        self.hover = False
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._activate)
        self.bind("<Return>", self._activate)
        self.bind("<space>", self._activate)

    def _enter(self, _event):
        self.hover = True
        self._draw()

    def _leave(self, _event):
        self.hover = False
        self._draw()

    def _activate(self, _event):
        self.command()

    def _draw(self, _event=None):
        self.delete("all")
        w, h = max(self.winfo_width(), 100), max(self.winfo_height(), 120)
        color = "#353658" if self.hover else CARD
        radius = 17
        # Rounded outline/body using native Tk primitives.
        self.create_rectangle(radius, 1, w-radius, h-1,
                              fill=color, outline="")
        self.create_rectangle(1, radius, w-1, h-radius,
                              fill=color, outline="")
        for cx, cy in ((radius, radius), (w-radius, radius),
                       (radius, h-radius), (w-radius, h-radius)):
            self.create_oval(cx-radius, cy-radius, cx+radius, cy+radius,
                             fill=color, outline="")
        self.create_text(20, 30, text=self.symbol, fill="#d2c4ff",
                         anchor="w", font=("Segoe UI Symbol", 19))
        self.create_text(20, 73, text=self.title_text, fill=FG,
                         anchor="w", font=("Segoe UI", 13, "bold"))
        for i, line in enumerate(self.subtitle.split("\n")):
            self.create_text(20, 101 + i*17, text=line,
                             fill=MUTED, anchor="w",
                             font=("Segoe UI", 9))


class PremiumChatSurface(ChatSurface):
    """A scenery-first welcome page that becomes a chat after first send."""

    LABELS = {
        "Mode latihan": "Offline demo (not AI)",
        "OpenRouter": "OpenRouter",
        "DeepSeek": "DeepSeek",
    }

    def __init__(self, parent, desktop, *, on_tasks=None, on_apps=None):
        self.on_tasks = on_tasks
        self.on_apps = on_apps
        self._conversation_open = False
        super().__init__(parent, desktop)

    def _build(self):
        self.configure(style="Premium.Chat.TFrame")
        style = ttk.Style(self)
        style.configure("Premium.Chat.TFrame", background=BG)
        style.configure(
            "Premium.Combo.TCombobox",
            fieldbackground=CARD, background=CARD, foreground=FG,
            arrowcolor=FG, selectbackground=CARD,
            selectforeground=FG, padding=6,
        )
        style.map(
            "Premium.Combo.TCombobox",
            fieldbackground=[("readonly", CARD)],
            foreground=[("readonly", FG)],
        )
        self.display_mode = tk.StringVar(master=self, value="Mode latihan")
        for label, actual in self.LABELS.items():
            if actual == self.mode.get():
                self.display_mode.set(label)
                break

        # Landing hero. The mountain vista is rendered locally in a Canvas,
        # so no network, tracking pixels or generated fake screenshots.
        self.landing = tk.Frame(self, bg=BG)
        self.landing.pack(fill="both", expand=True)
        self.hero = TwilightBanner(self.landing, height=330)
        self.hero.pack(fill="x")

        # Composer positioned inside the scenic hero, like the reference.
        # Its parent remains self so it can be packed at the bottom after send.
        self.composer = tk.Frame(
            self, bg="#262840", highlightbackground="#6e628e",
            highlightthickness=1,
        )
        self.composer.place(
            in_=self.hero, relx=.045, rely=.625,
            relwidth=.91, height=117,
        )
        self.input = tk.Text(
            self.composer, height=2, wrap="word",
            bg="#262840", fg=FG, insertbackground=FG,
            selectbackground="#554c86", font=("Segoe UI", 11),
            padx=13, pady=9, relief="flat",
            highlightthickness=0, bd=0,
        )
        self.input.pack(side="top", fill="x", expand=True)
        self.input.bind(
            "<Control-Return>",
            lambda event: (self.send_message(), "break")[1],
        )
        bottom = tk.Frame(self.composer, bg="#262840")
        bottom.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(
            bottom, text="+", bg="#343653", fg=FG,
            font=("Segoe UI", 14), padx=8,
        ).pack(side="left", padx=(0, 8))
        self.model_box = ttk.Combobox(
            bottom, state="readonly", width=18,
            values=list(self.LABELS.keys()),
            textvariable=self.display_mode,
            style="Premium.Combo.TCombobox",
            font=("Segoe UI", 10),
        )
        self.model_box.pack(side="left")
        self.model_box.bind("<<ComboboxSelected>>", self._select_mode)
        self.send = tk.Button(
            bottom, text="➤", font=("Segoe UI Symbol", 16, "bold"),
            bg=PURPLE, fg="#ffffff", relief="flat", bd=0,
            activebackground="#ad86f9", activeforeground="#ffffff",
            padx=15, pady=4, cursor="hand2",
            command=self.send_message,
        )
        self.send.pack(side="right")
        # Preserve the explicit network gate for real API calls, but do not
        # visually burden users in offline mode.
        self.live_permission = tk.Checkbutton(
            bottom, variable=self.allow_network,
            text="Izinkan 1 jawaban online",
            bg="#262840", fg="#d7cfee",
            selectcolor="#373753", activebackground="#262840",
            activeforeground=FG, font=("Segoe UI", 9),
        )
        if self.mode.get() != "Offline demo (not AI)":
            self.live_permission.pack(side="right", padx=(0, 10),
                                      before=self.send)

        self.cards = tk.Frame(self.landing, bg=BG)
        self.cards.pack(fill="x", padx=22, pady=(17, 0))
        for index, spec in enumerate((
            ("Tugas", "Kelola dan pantau\npekerjaan", "☑", self._go_tasks),
            ("Aplikasi", "Hubungkan\naplikasi favorit", "▦", self._go_apps),
            ("Template", "Gunakan alur siap\npakai", "◇", self._template),
        )):
            name, desc, icon, callback = spec
            card = QuickCard(self.cards, name, desc, icon, callback)
            card.grid(row=0, column=index, sticky="nsew",
                      padx=(0, 9) if index < 2 else (0, 0))
            self.cards.columnconfigure(index, weight=1, uniform="cards")

        self.landing_status = tk.Label(
            self.landing, textvariable=self.status, bg=BG,
            fg="#a49dbb", font=("Segoe UI", 9),
            wraplength=650, justify="left", anchor="w",
        )
        self.landing_status.pack(fill="x", padx=26, pady=(14, 0))
        # Transcript exists even before first send for accessibility/tests.
        # It is not shown until the owner begins an actual conversation.
        self.chat_area = tk.Frame(self, bg=BG)
        toolbar = tk.Frame(self.chat_area, bg=BG)
        toolbar.pack(fill="x", pady=(4, 12))
        tk.Label(
            toolbar, text="Percakapan", bg=BG, fg=FG,
            font=("Segoe UI", 19, "bold"),
        ).pack(side="left")
        tk.Button(
            toolbar, text="Pengaturan AI",
            command=self.open_settings, bg=CARD, fg=FG,
            activebackground="#393759", activeforeground=FG,
            relief="flat", bd=0, padx=13, pady=7, cursor="hand2",
            font=("Segoe UI", 9),
        ).pack(side="right")
        chat_holder = tk.Frame(self.chat_area, bg="#191e35")
        chat_holder.pack(fill="both", expand=True)
        self.chat = tk.Text(
            chat_holder, bg="#191e35", fg=FG,
            font=("Segoe UI", 11), relief="flat",
            padx=25, pady=20, wrap="word",
            highlightthickness=0, borderwidth=0, state="disabled",
            insertbackground=FG,
        )
        self.chat.pack(side="left", fill="both", expand=True)
        scroll = tk.Scrollbar(chat_holder, command=self.chat.yview, width=10)
        scroll.pack(side="right", fill="y")
        self.chat.configure(yscrollcommand=scroll.set)
        self._append(
            "VARYN",
            "Selamat datang. Tulis pesanmu di bawah. Mode latihan tidak "
            "menghasilkan jawaban AI sungguhan.",
        )
        self.chat_status = tk.Label(
            self, textvariable=self.status, bg=BG, fg=MUTED,
            font=("Segoe UI", 9), justify="left", anchor="w",
        )

    def _select_mode(self, _event=None):
        selected = self.LABELS.get(self.display_mode.get())
        if selected is None:
            return
        self.mode.set(selected)
        self._mode_changed()
        if selected == "Offline demo (not AI)":
            self.live_permission.pack_forget()
        else:
            self.live_permission.pack(side="right", padx=(0, 10),
                                      before=self.send)

    def _go_tasks(self):
        if callable(self.on_tasks):
            self.on_tasks()

    def _go_apps(self):
        if callable(self.on_apps):
            self.on_apps()

    def _template(self):
        if self._busy or self._closed:
            return
        self.input.delete("1.0", "end")
        self.input.insert(
            "1.0",
            "Bantu saya membuat rencana pekerjaan minggu ini. "
            "Mulai dari tiga prioritas terpenting.",
        )
        self.input.focus_set()
        self.status.set("Template dimasukkan. Periksa pesannya sebelum mengirim.")

    def _activate_conversation(self):
        if self._conversation_open or self._closed:
            return
        self._conversation_open = True
        self.composer.place_forget()
        self.landing.pack_forget()
        self.composer.pack(side="bottom", fill="x", padx=8, pady=(12, 4))
        self.chat_status.pack(side="bottom", fill="x", padx=12,
                              pady=(0, 10))
        self.chat_area.pack(side="top", fill="both", expand=True)
        self.input.focus_set()

    def send_message(self):
        if self._closed or self._busy:
            return
        before = self.chat.get("1.0", "end")
        super().send_message()
        after = self.chat.get("1.0", "end")
        # User content is appended only once a simulated send or an actually
        # reviewed live send is accepted. Validation/denial stays on home.
        if after != before and "\nYou\n" in after:
            self._activate_conversation()
