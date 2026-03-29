
import json
import math
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False

APP_TITLE = "MBÇ Mühendislik • Kar Yükü Hesap Aracı V2"
APP_VERSION = "2.0"
BG = "#F4F7FB"
CARD = "#FFFFFF"
PRIMARY = "#124C8C"
ACCENT = "#E67828"
TEXT = "#243041"
MUTED = "#64748B"

def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)

def load_json(name):
    with open(resource_path(name), "r", encoding="utf-8") as f:
        return json.load(f)

REGIONS_DB = load_json("regions.json")
SK_TABLE = load_json("sk_table.json")

def interpolate_sk(region: str, altitude: float) -> float:
    pts = SK_TABLE[str(region)]
    pts = sorted(pts, key=lambda x: x[0])
    if altitude <= pts[0][0]:
        return float(pts[0][1])
    if altitude >= pts[-1][0]:
        # linear extrapolation on last segment
        x1, y1 = pts[-2]
        x2, y2 = pts[-1]
        if x2 == x1:
            return float(y2)
        return round(y1 + (altitude - x1) * (y2 - y1) / (x2 - x1), 3)
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        if x1 <= altitude <= x2:
            if x2 == x1:
                return float(y1)
            return round(y1 + (altitude - x1) * (y2 - y1) / (x2 - x1), 3)
    return float(pts[-1][1])

def mono_mu(alpha, parapet_or_guard=False):
    if alpha <= 30:
        mu1 = 0.8
    elif alpha < 60:
        mu1 = 0.8 * (60 - alpha) / 30
    else:
        mu1 = 0.0
    if parapet_or_guard:
        mu1 = max(mu1, 0.8)
    return round(mu1, 3)

def mu2_table(alpha):
    if alpha <= 30:
        return round(0.8 + 0.8 * alpha / 30.0, 3)
    if alpha < 60:
        return 1.6
    return 1.6

def cylindrical_mu(h, b, beta):
    if beta > 60:
        return 0.0
    mu = 0.2 + 10 * h / max(b, 1e-9)
    return round(min(mu, 2.0), 3)

def obstacle_mu2(h, sk, gamma=2.0):
    mu2 = gamma * h / max(sk, 1e-9)
    return round(min(max(mu2, 0.8), 2.0), 3)

def drift_length(h):
    return max(5.0, min(2.0 * h, 15.0))

def adjacent_mu(alpha_upper, b1, b2, h, sk):
    mu_s = 0.0 if alpha_upper <= 15 else 0.5 * mu2_table(alpha_upper)
    mu_w_raw = (b1 + b2) / max(2 * h, 1e-9)
    mu_w_limit = 2.0 * h / max(sk, 1e-9)
    mu_w = min(mu_w_raw, mu_w_limit)
    mu_w = min(max(mu_w, 0.8), 4.0)
    return round(mu_s + mu_w, 3), round(mu_s, 3), round(mu_w, 3)

def edge_overhang_load(s, d, gamma=3.0):
    # recommended k = 3/d, additionally limited by d*gamma
    if d <= 0:
        return 0.0, 0.0
    k = min(3.0 / d, d * gamma)
    se = k * s * s / gamma
    return round(k, 3), round(se, 3)

class SnowApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1420x860")
        self.root.minsize(1250, 780)
        self.root.configure(bg=BG)

        self.results = {}
        self.md_report_cache = ""

        self._build_style()
        self._build_layout()
        self._populate_cities()
        self.update_region_preview()
        self.on_roof_type_change()

    def _build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=BG, foreground=TEXT, font=("Segoe UI Semibold", 20))
        style.configure("Sub.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=CARD, foreground=TEXT, font=("Segoe UI Semibold", 11))
        style.configure("BigValue.TLabel", background=CARD, foreground=PRIMARY, font=("Segoe UI Semibold", 18))
        style.configure("TButton", font=("Segoe UI", 10), padding=8)
        style.map("TButton", background=[("active", "#DBEAFE")])
        style.configure("Accent.TButton", background=PRIMARY, foreground="white")
        style.map("Accent.TButton", background=[("active", "#0F3D72")], foreground=[("active", "white")])
        style.configure("Treeview", font=("Segoe UI", 10), rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 10))
        style.configure("TLabelframe", background=CARD, foreground=TEXT)
        style.configure("TLabelframe.Label", background=CARD, foreground=TEXT, font=("Segoe UI Semibold", 10))

    def _build_layout(self):
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=18, pady=(14, 10))

        logo_path = resource_path("assets/mbc_logo.png")
        self.logo_img = tk.PhotoImage(file=logo_path)
        tk.Label(top, image=self.logo_img, bg=BG).pack(side="left", padx=(0, 12))
        title_box = ttk.Frame(top)
        title_box.pack(side="left", fill="x", expand=True)
        ttk.Label(title_box, text="MBÇ Mühendislik", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_box, text="TS EN 1991-1-3 uyumlu kar yükü hesaplama, yük durumu üretimi ve raporlama", style="Sub.TLabel").pack(anchor="w")
        ttk.Label(top, text=f"Sürüm {APP_VERSION}", style="Sub.TLabel").pack(side="right", anchor="ne")

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True, padx=18, pady=(0, 16))

        left = ttk.Frame(body, style="Card.TFrame")
        left.pack(side="left", fill="y", padx=(0, 10))
        left.configure(width=520)
        left.pack_propagate(False)

        right = ttk.Frame(body, style="Card.TFrame")
        right.pack(side="left", fill="both", expand=True)

        self._build_left_panel(left)
        self._build_right_panel(right)

    def _build_left_panel(self, parent):
        canvas = tk.Canvas(parent, bg=CARD, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)
        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        win = canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(12,0), pady=12)
        scrollbar.pack(side="right", fill="y", pady=12)

        self.vars = {
            "city": tk.StringVar(),
            "district": tk.StringVar(),
            "region": tk.StringVar(value="I"),
            "altitude": tk.StringVar(value="0"),
            "manual_sk": tk.StringVar(),
            "roof_type": tk.StringVar(value="Tek eğimli"),
            "alpha": tk.StringVar(value="20"),
            "alpha2": tk.StringVar(value="20"),
            "beta": tk.StringVar(value="40"),
            "span_b": tk.StringVar(value="12"),
            "length_l": tk.StringVar(value="24"),
            "height_h": tk.StringVar(value="2"),
            "b1": tk.StringVar(value="6"),
            "b2": tk.StringVar(value="8"),
            "ce": tk.StringVar(value="1.0"),
            "ct": tk.StringVar(value="1.0"),
            "topography": tk.StringVar(value="Normal"),
            "thermal_desc": tk.StringVar(value="Standart"),
            "parapet": tk.BooleanVar(value=False),
            "parapet_h": tk.StringVar(value="0.0"),
            "snow_guard": tk.BooleanVar(value=False),
            "obstacle": tk.BooleanVar(value=False),
            "obstacle_h": tk.StringVar(value="0.5"),
            "adjacent": tk.BooleanVar(value=False),
            "exceptional": tk.BooleanVar(value=False),
            "cesi": tk.StringVar(value="2.0"),
            "edge_overhang": tk.BooleanVar(value=False),
            "snow_depth_d": tk.StringVar(value="0.3"),
            "project_name": tk.StringVar(value="Kar Yükü Çalışması"),
            "client_name": tk.StringVar(value=""),
            "engineer_name": tk.StringVar(value="MBÇ Mühendislik"),
        }

        self._section_project(scrollable)
        self._section_location(scrollable)
        self._section_geometry(scrollable)
        self._section_coefficients(scrollable)
        self._section_special(scrollable)

        btns = ttk.Frame(scrollable, style="Card.TFrame")
        btns.pack(fill="x", pady=(8, 16))
        ttk.Button(btns, text="Hesapla", style="Accent.TButton", command=self.calculate).pack(side="left", fill="x", expand=True, padx=(0,6))
        ttk.Button(btns, text="Temizle", command=self.reset_form).pack(side="left", fill="x", expand=True, padx=(6,6))
        ttk.Button(btns, text="Markdown Rapor", command=self.export_markdown).pack(side="left", fill="x", expand=True, padx=(6,6))
        ttk.Button(btns, text="PDF Rapor", command=self.export_pdf).pack(side="left", fill="x", expand=True, padx=(6,0))

    def _card_labelframe(self, parent, text):
        lf = ttk.LabelFrame(parent, text=text, padding=12, style="TLabelframe")
        lf.pack(fill="x", pady=6)
        return lf

    def _row(self, parent, label, widget, row):
        ttk.Label(parent, text=label, background=CARD).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=6)
        widget.grid(row=row, column=1, sticky="ew", pady=6)
        parent.grid_columnconfigure(1, weight=1)

    def _section_project(self, parent):
        lf = self._card_labelframe(parent, "1. Proje Bilgileri")
        self._row(lf, "Proje adı", ttk.Entry(lf, textvariable=self.vars["project_name"]), 0)
        self._row(lf, "Müşteri", ttk.Entry(lf, textvariable=self.vars["client_name"]), 1)
        self._row(lf, "Hazırlayan", ttk.Entry(lf, textvariable=self.vars["engineer_name"]), 2)

    def _section_location(self, parent):
        lf = self._card_labelframe(parent, "2. Lokasyon ve zemin kar yükü")
        self.city_combo = ttk.Combobox(lf, textvariable=self.vars["city"], state="readonly")
        self.city_combo.bind("<<ComboboxSelected>>", lambda e: self._populate_districts())
        self._row(lf, "İl", self.city_combo, 0)

        self.district_combo = ttk.Combobox(lf, textvariable=self.vars["district"], state="readonly")
        self.district_combo.bind("<<ComboboxSelected>>", lambda e: self.update_region_preview())
        self._row(lf, "İlçe", self.district_combo, 1)

        region_row = ttk.Frame(lf)
        ttk.Combobox(region_row, textvariable=self.vars["region"], values=["I","II","III","IV"], state="readonly", width=8).pack(side="left")
        ttk.Button(region_row, text="İlden otomatik çek", command=self.update_region_preview).pack(side="left", padx=8)
        self._row(lf, "Kar bölgesi", region_row, 2)

        self._row(lf, "Rakım A (m)", ttk.Entry(lf, textvariable=self.vars["altitude"]), 3)
        self._row(lf, "sₖ override (kN/m²)", ttk.Entry(lf, textvariable=self.vars["manual_sk"]), 4)

        self.region_info = ttk.Label(lf, text="Bölge bilgisi hazır", background=CARD, foreground=MUTED)
        self.region_info.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6,2))

    def _section_geometry(self, parent):
        lf = self._card_labelframe(parent, "3. Çatı geometrisi")
        roof_values = ["Tek eğimli", "Çift eğimli", "Çok açıklıklı", "Silindirik", "Yüksek yapıya bitişik"]
        roof_combo = ttk.Combobox(lf, textvariable=self.vars["roof_type"], values=roof_values, state="readonly")
        roof_combo.bind("<<ComboboxSelected>>", lambda e: self.on_roof_type_change())
        self._row(lf, "Çatı tipi", roof_combo, 0)

        self.alpha_entry = ttk.Entry(lf, textvariable=self.vars["alpha"])
        self._row(lf, "α₁ eğimi (°)", self.alpha_entry, 1)

        self.alpha2_entry = ttk.Entry(lf, textvariable=self.vars["alpha2"])
        self._row(lf, "α₂ eğimi (°)", self.alpha2_entry, 2)

        self.beta_entry = ttk.Entry(lf, textvariable=self.vars["beta"])
        self._row(lf, "β (silindirik için)", self.beta_entry, 3)

        self.span_entry = ttk.Entry(lf, textvariable=self.vars["span_b"])
        self._row(lf, "Açıklık b (m)", self.span_entry, 4)
        self._row(lf, "Çatı uzunluğu L (m)", ttk.Entry(lf, textvariable=self.vars["length_l"]), 5)
        self._row(lf, "Yükseklik h (m)", ttk.Entry(lf, textvariable=self.vars["height_h"]), 6)

        self.b1_entry = ttk.Entry(lf, textvariable=self.vars["b1"])
        self._row(lf, "b₁ (üst/komşu çatı)", self.b1_entry, 7)
        self.b2_entry = ttk.Entry(lf, textvariable=self.vars["b2"])
        self._row(lf, "b₂ (alt çatı)", self.b2_entry, 8)

    def _section_coefficients(self, parent):
        lf = self._card_labelframe(parent, "4. Maruz kalma ve ısı katsayıları")

        topo = ttk.Frame(lf)
        topo_combo = ttk.Combobox(topo, textvariable=self.vars["topography"], values=["Rüzgara açık", "Normal", "Korunmuş"], state="readonly", width=18)
        topo_combo.pack(side="left")
        topo_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_topography())
        ttk.Entry(topo, textvariable=self.vars["ce"], width=10).pack(side="left", padx=8)
        self._row(lf, "Topografya / Cₑ", topo, 0)

        therm = ttk.Frame(lf)
        therm_combo = ttk.Combobox(therm, textvariable=self.vars["thermal_desc"], values=["Standart", "Yüksek ısı kaybı / cam çatı"], state="readonly", width=24)
        therm_combo.pack(side="left")
        therm_combo.bind("<<ComboboxSelected>>", lambda e: self.apply_thermal())
        ttk.Entry(therm, textvariable=self.vars["ct"], width=10).pack(side="left", padx=8)
        self._row(lf, "Isı durumu / Cₜ", therm, 1)

    def _section_special(self, parent):
        lf = self._card_labelframe(parent, "5. Özel durumlar")
        row = 0
        ttk.Checkbutton(lf, text="Parapet var", variable=self.vars["parapet"], command=self.on_special_toggle).grid(row=row, column=0, sticky="w")
        ttk.Entry(lf, textvariable=self.vars["parapet_h"], width=12).grid(row=row, column=1, sticky="w")
        ttk.Label(lf, text="Parapet yüksekliği (m)", background=CARD).grid(row=row, column=2, sticky="w"); row += 1

        ttk.Checkbutton(lf, text="Kar tutucu var", variable=self.vars["snow_guard"], command=self.on_special_toggle).grid(row=row, column=0, sticky="w"); row += 1

        ttk.Checkbutton(lf, text="Çatı üzerinde engel/çıkıntı var", variable=self.vars["obstacle"], command=self.on_special_toggle).grid(row=row, column=0, sticky="w")
        ttk.Entry(lf, textvariable=self.vars["obstacle_h"], width=12).grid(row=row, column=1, sticky="w")
        ttk.Label(lf, text="Engel yüksekliği h (m)", background=CARD).grid(row=row, column=2, sticky="w"); row += 1

        ttk.Checkbutton(lf, text="Çatı kenarı kar sarkıntısı kontrolü", variable=self.vars["edge_overhang"], command=self.on_special_toggle).grid(row=row, column=0, sticky="w")
        ttk.Entry(lf, textvariable=self.vars["snow_depth_d"], width=12).grid(row=row, column=1, sticky="w")
        ttk.Label(lf, text="Kar tabakası derinliği d (m)", background=CARD).grid(row=row, column=2, sticky="w"); row += 1

        ttk.Checkbutton(lf, text="İstisnai kar durumu", variable=self.vars["exceptional"], command=self.on_special_toggle).grid(row=row, column=0, sticky="w")
        ttk.Entry(lf, textvariable=self.vars["cesi"], width=12).grid(row=row, column=1, sticky="w")
        ttk.Label(lf, text="Cₑsi", background=CARD).grid(row=row, column=2, sticky="w"); row += 1

        lf.grid_columnconfigure(2, weight=1)

    def _build_right_panel(self, parent):
        header = ttk.Frame(parent, style="Card.TFrame")
        header.pack(fill="x", padx=14, pady=(14,10))
        self.summary_cards = []
        for title in ["sₖ", "μ kritik", "s kritik", "Load case"]:
            card = tk.Frame(header, bg="#EEF4FC", highlightthickness=0, bd=0)
            card.pack(side="left", fill="x", expand=True, padx=6)
            tk.Label(card, text=title, bg="#EEF4FC", fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", padx=14, pady=(12,0))
            val = tk.Label(card, text="—", bg="#EEF4FC", fg=PRIMARY, font=("Segoe UI Semibold", 20))
            val.pack(anchor="w", padx=14, pady=(2,12))
            self.summary_cards.append(val)

        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True, padx=14, pady=(0,14))

        tab_results = ttk.Frame(notebook, style="Card.TFrame")
        tab_report = ttk.Frame(notebook, style="Card.TFrame")
        tab_diagram = ttk.Frame(notebook, style="Card.TFrame")
        notebook.add(tab_results, text="Sonuçlar")
        notebook.add(tab_report, text="Rapor Önizleme")
        notebook.add(tab_diagram, text="Yük Şeması")

        cols = ("case", "mu", "ce", "ct", "sk", "s", "note")
        self.tree = ttk.Treeview(tab_results, columns=cols, show="headings")
        headings = {
            "case":"Yük durumu", "mu":"μ", "ce":"Cₑ", "ct":"Cₜ", "sk":"sₖ", "s":"s (kN/m²)", "note":"Açıklama"
        }
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=120 if c!="note" else 320, anchor="center")
        self.tree.column("note", anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.report_text = tk.Text(tab_report, wrap="word", font=("Consolas", 11), bg="#FBFDFF", fg=TEXT)
        self.report_text.pack(fill="both", expand=True, padx=10, pady=10)

        self.diagram_canvas = tk.Canvas(tab_diagram, bg="#FBFDFF", highlightthickness=0)
        self.diagram_canvas.pack(fill="both", expand=True, padx=10, pady=10)
        self.diagram_canvas.bind("<Configure>", lambda e: self.draw_diagram())

    def _populate_cities(self):
        cities = sorted(REGIONS_DB.keys())
        self.city_combo["values"] = cities
        if cities:
            self.vars["city"].set(cities[0])
            self._populate_districts()

    def _populate_districts(self):
        city = self.vars["city"].get()
        dcts = sorted((REGIONS_DB.get(city) or {}).get("districts", {}).keys())
        self.district_combo["values"] = dcts
        if dcts:
            self.vars["district"].set(dcts[0])
        else:
            self.vars["district"].set("")
        self.update_region_preview()

    def update_region_preview(self):
        city = self.vars["city"].get()
        district = self.vars["district"].get()
        region = None
        if city in REGIONS_DB:
            region = REGIONS_DB[city]["districts"].get(district) or REGIONS_DB[city].get("region")
        if region:
            self.vars["region"].set(region)
            msg = f"Otomatik bölge: {city} / {district or 'merkez'} → Bölge {region}"
        else:
            msg = "İl/ilçe bulunamadı. Bölgeyi manuel seçebilirsiniz."
        self.region_info.config(text=msg)

    def apply_topography(self):
        m = {"Rüzgara açık":"0.8", "Normal":"1.0", "Korunmuş":"1.2"}
        self.vars["ce"].set(m.get(self.vars["topography"].get(), "1.0"))

    def apply_thermal(self):
        m = {"Standart":"1.0", "Yüksek ısı kaybı / cam çatı":"0.8"}
        self.vars["ct"].set(m.get(self.vars["thermal_desc"].get(), "1.0"))

    def on_special_toggle(self):
        pass

    def on_roof_type_change(self):
        roof = self.vars["roof_type"].get()
        show_alpha2 = roof in ("Çift eğimli", "Çok açıklıklı")
        show_beta = roof == "Silindirik"
        show_adj = roof == "Yüksek yapıya bitişik"

        self.alpha2_entry.configure(state="normal" if show_alpha2 else "disabled")
        self.beta_entry.configure(state="normal" if show_beta else "disabled")
        self.b1_entry.configure(state="normal" if show_adj else "disabled")
        self.b2_entry.configure(state="normal" if show_adj else "disabled")

    def parse_float(self, key, label):
        try:
            return float(self.vars[key].get().replace(",", "."))
        except Exception:
            raise ValueError(f"{label} değeri geçersiz.")

    def calculate(self):
        try:
            city = self.vars["city"].get()
            district = self.vars["district"].get()
            region = self.vars["region"].get()
            altitude = self.parse_float("altitude", "Rakım")
            alpha = self.parse_float("alpha", "α₁")
            alpha2 = self.parse_float("alpha2", "α₂")
            beta = self.parse_float("beta", "β")
            b = self.parse_float("span_b", "Açıklık b")
            L = self.parse_float("length_l", "Uzunluk L")
            h = self.parse_float("height_h", "Yükseklik h")
            b1 = self.parse_float("b1", "b₁")
            b2 = self.parse_float("b2", "b₂")
            ce = self.parse_float("ce", "Cₑ")
            ct = self.parse_float("ct", "Cₜ")
            parapet_h = self.parse_float("parapet_h", "Parapet yüksekliği")
            obstacle_h = self.parse_float("obstacle_h", "Engel yüksekliği")
            cesi = self.parse_float("cesi", "Cₑsi")
            snow_depth_d = self.parse_float("snow_depth_d", "Kar derinliği d")

            manual_sk = self.vars["manual_sk"].get().strip()
            if manual_sk:
                sk = float(manual_sk.replace(",", "."))
                sk_source = "Kullanıcı override"
            else:
                sk = interpolate_sk(region, altitude)
                sk_source = f"Bölge {region} + rakım interpolasyonu"

            roof = self.vars["roof_type"].get()
            parapet_or_guard = self.vars["parapet"].get() or self.vars["snow_guard"].get()

            cases = []
            notes = []
            mu_values = {}

            if roof == "Tek eğimli":
                mu1 = mono_mu(alpha, parapet_or_guard)
                mu_values["μ1"] = mu1
                cases.append(("Uniform", mu1, "Madde 5.3.2"))
                cases.append(("Birikmiş", mu2_table(alpha), "Çizelge 5.2 / Şekil 5.2"))
            elif roof == "Çift eğimli":
                mu_left = mono_mu(alpha, parapet_or_guard)
                mu_right = mono_mu(alpha2, parapet_or_guard)
                mu_values["μ1(sol)"] = mu_left
                mu_values["μ1(sağ)"] = mu_right
                cases.append(("Simetrik", max(mu_left, mu_right), "Şekil 5.3 durum (i)"))
                cases.append(("Drift sol", max(0.5 * mu_left, mu_right), "Şekil 5.3 durum (ii)"))
                cases.append(("Drift sağ", max(mu_left, 0.5 * mu_right), "Şekil 5.3 durum (iii)"))
            elif roof == "Çok açıklıklı":
                mu_a = mono_mu(alpha, parapet_or_guard)
                mu_b = mono_mu(alpha2, parapet_or_guard)
                mu_bar = mu2_table((alpha + alpha2) / 2)
                mu_values["μ1(α1)"] = mu_a
                mu_values["μ1(α2)"] = mu_b
                mu_values["μ2(ortalama)"] = mu_bar
                cases.append(("Uniform", max(mu_a, mu_b), "Şekil 5.4 durum (i)"))
                cases.append(("Vadi birikmesi", mu_bar, "Şekil 5.4 durum (ii)"))
            elif roof == "Silindirik":
                mu3 = cylindrical_mu(h, b, beta)
                mu_values["μ3"] = mu3
                cases.append(("Uniform", 0.8, "Şekil 5.6 durum (i)"))
                cases.append(("Birikmiş", mu3, "Madde 5.3.5 / Şekil 5.6 durum (ii)"))
            elif roof == "Yüksek yapıya bitişik":
                mu1 = 0.8
                mu2, mu_s, mu_w = adjacent_mu(alpha, b1, b2, h, sk)
                mu_values["μ1"] = mu1
                mu_values["μs"] = mu_s
                mu_values["μw"] = mu_w
                mu_values["μ2"] = mu2
                cases.append(("Uniform", mu1, "Madde 5.3.6 / durum (i)"))
                cases.append(("Birikmiş drift", mu2, "Madde 5.3.6 / durum (ii)"))
                notes.append(f"lₛ = {drift_length(h):.2f} m")
            else:
                raise ValueError("Çatı tipi seçilmelidir.")

            if self.vars["obstacle"].get():
                mu_ob = obstacle_mu2(obstacle_h, sk)
                mu_values["μ_engel"] = mu_ob
                cases.append(("Engel birikmesi", mu_ob, "Madde 6.2"))

            if self.vars["parapet"].get() and parapet_h > 0:
                mu_par = obstacle_mu2(parapet_h, sk)
                mu_values["μ_parapet"] = mu_par
                cases.append(("Parapet birikmesi", mu_par, "Ek B / Madde 6.2 mantığı"))

            if self.vars["exceptional"].get():
                s_ad = round(cesi * sk, 3)
                cases.append(("İstisnai durum", 1.0, f"sAd = {s_ad:.3f} kN/m²"))
            else:
                s_ad = None

            result_rows = []
            critical_s = -1
            critical_case = "-"
            critical_mu = 0

            for case_name, mu, ref in cases:
                if case_name == "İstisnai durum" and s_ad is not None:
                    s = round(mu * s_ad, 3)
                    result_rows.append((case_name, mu, 1.0, 1.0, s_ad, s, ref))
                else:
                    s = round(mu * ce * ct * sk, 3)
                    result_rows.append((case_name, round(mu,3), ce, ct, sk, s, ref))
                if s > critical_s:
                    critical_s = s
                    critical_case = case_name
                    critical_mu = mu

            overhang = None
            if self.vars["edge_overhang"].get():
                k, se = edge_overhang_load(critical_s, snow_depth_d)
                overhang = {"k": k, "Se": se}
                notes.append(f"Çatı kenarı kar sarkıntısı Se = {se:.3f} kN/m (k={k:.3f})")

            self.results = {
                "project_name": self.vars["project_name"].get(),
                "client_name": self.vars["client_name"].get(),
                "engineer_name": self.vars["engineer_name"].get(),
                "city": city, "district": district, "region": region, "altitude": altitude,
                "roof": roof, "alpha": alpha, "alpha2": alpha2, "beta": beta, "b": b, "L": L, "h": h,
                "ce": ce, "ct": ct, "sk": sk, "sk_source": sk_source, "s_ad": s_ad,
                "mu_values": mu_values, "rows": result_rows, "critical_s": critical_s,
                "critical_case": critical_case, "critical_mu": critical_mu, "notes": notes,
                "overhang": overhang,
                "specials": {
                    "parapet": self.vars["parapet"].get(),
                    "snow_guard": self.vars["snow_guard"].get(),
                    "obstacle": self.vars["obstacle"].get(),
                    "exceptional": self.vars["exceptional"].get()
                },
                "generated_at": datetime.now().strftime("%d.%m.%Y %H:%M")
            }
            self.render_results()
        except Exception as e:
            messagebox.showerror("Hesap Hatası", str(e))

    def render_results(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self.results["rows"]:
            self.tree.insert("", "end", values=row)

        self.summary_cards[0].config(text=f'{self.results["sk"]:.3f} kN/m²')
        self.summary_cards[1].config(text=f'{self.results["critical_mu"]:.3f}')
        self.summary_cards[2].config(text=f'{self.results["critical_s"]:.3f} kN/m²')
        self.summary_cards[3].config(text=self.results["critical_case"])

        md = self.generate_markdown()
        self.md_report_cache = md
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", md)
        self.draw_diagram()

    def draw_diagram(self):
        c = self.diagram_canvas
        c.delete("all")
        w = c.winfo_width()
        h = c.winfo_height()
        if w < 100 or h < 100:
            return

        roof = self.vars["roof_type"].get()
        critical = self.results.get("critical_case", "—")
        critical_s = self.results.get("critical_s", 0.0)
        c.create_text(30, 20, anchor="w", text=f"Kritik yük durumu: {critical} — {critical_s:.3f} kN/m²", fill=TEXT, font=("Segoe UI Semibold", 12))

        x0, y0 = 100, h * 0.72
        x1 = w - 90
        roof_top = h * 0.38
        b = max(float(self.vars["span_b"].get().replace(",", ".")), 1.0)
        alpha = float(self.vars["alpha"].get().replace(",", "."))
        alpha2 = float(self.vars["alpha2"].get().replace(",", "."))
        span = x1 - x0

        def draw_load_band(xa, ya, xb, yb, depth=38, label="μ"):
            poly = [xa, ya-depth, xb, yb-depth, xb, yb, xa, ya]
            c.create_polygon(poly, fill="#CFE3FB", outline="#97B9E8")
            c.create_text((xa+xb)/2, min(ya, yb)-depth-12, text=label, fill=PRIMARY, font=("Segoe UI", 10, "bold"))

        if roof == "Tek eğimli":
            rise = math.tan(math.radians(alpha)) * span * 0.25
            xa, ya = x0, roof_top + rise
            xb, yb = x1, roof_top
            c.create_line(x0, y0, xa, ya, width=4, fill=TEXT)
            c.create_line(x1, y0, xb, yb, width=4, fill=TEXT)
            c.create_line(xa, ya, xb, yb, width=5, fill=TEXT)
            draw_load_band(xa, ya, xb, yb, label=critical)
        elif roof in ("Çift eğimli", "Çok açıklıklı", "Yüksek yapıya bitişik"):
            mid = (x0 + x1) / 2
            rise1 = math.tan(math.radians(alpha)) * span * 0.12
            rise2 = math.tan(math.radians(alpha2)) * span * 0.12
            ridge_y = roof_top
            left_y = ridge_y + rise1
            right_y = ridge_y + rise2
            c.create_line(x0, y0, x0, left_y, width=4, fill=TEXT)
            c.create_line(x1, y0, x1, right_y, width=4, fill=TEXT)
            c.create_line(x0, left_y, mid, ridge_y, width=5, fill=TEXT)
            c.create_line(mid, ridge_y, x1, right_y, width=5, fill=TEXT)
            if "sol" in critical.lower():
                draw_load_band(x0, left_y, mid, ridge_y, label=critical)
            elif "sağ" in critical.lower():
                draw_load_band(mid, ridge_y, x1, right_y, label=critical)
            elif "drift" in critical.lower() or "birikmiş" in critical.lower():
                draw_load_band(x0, left_y, mid, ridge_y, label="0.5μ")
                draw_load_band(mid, ridge_y, x1, right_y, label="μ")
            else:
                draw_load_band(x0, left_y, mid, ridge_y, label="μ")
                draw_load_band(mid, ridge_y, x1, right_y, label="μ")
        elif roof == "Silindirik":
            left, right = x0, x1
            top_y = roof_top + 40
            c.create_line(left, y0, left, top_y, width=4, fill=TEXT)
            c.create_line(right, y0, right, top_y, width=4, fill=TEXT)
            c.create_arc(left, top_y-100, right, top_y+100, start=0, extent=180, style="arc", width=5, outline=TEXT)
            draw_load_band(left+50, top_y-70, right-50, top_y-70, label=critical)

        if self.results.get("overhang"):
            c.create_text(30, 48, anchor="w",
                          text=f'Çatı kenarı sarkıntısı Se = {self.results["overhang"]["Se"]:.3f} kN/m',
                          fill=ACCENT, font=("Segoe UI", 10, "bold"))

    def generate_markdown(self):
        r = self.results
        if not r:
            return "Önce hesap yapınız."
        lines = []
        lines.append(f"# {r['project_name']}")
        lines.append("")
        lines.append("## 1. Genel Bilgiler")
        lines.append(f"- **Hazırlayan:** {r['engineer_name']}")
        if r["client_name"]:
            lines.append(f"- **Müşteri:** {r['client_name']}")
        lines.append(f"- **Tarih:** {r['generated_at']}")
        lines.append(f"- **Lokasyon:** {r['city']} / {r['district']} — Bölge {r['region']}")
        lines.append(f"- **Rakım:** {r['altitude']:.1f} m")
        lines.append("")
        lines.append("## 2. Kullanılan Esaslar")
        lines.append("- TS EN 1991-1-3 / Eurocode 1 Kar Yükleri")
        lines.append("- Temel bağıntı: **s = μ · Cₑ · Cₜ · sₖ**")
        lines.append(f"- **sₖ kaynağı:** {r['sk_source']}")
        lines.append("")
        lines.append("## 3. Girdiler")
        lines.append(f"- **Çatı tipi:** {r['roof']}")
        lines.append(f"- **α₁:** {r['alpha']}°")
        if r["roof"] in ("Çift eğimli", "Çok açıklıklı"):
            lines.append(f"- **α₂:** {r['alpha2']}°")
        if r["roof"] == "Silindirik":
            lines.append(f"- **β:** {r['beta']}°")
        lines.append(f"- **Açıklık b:** {r['b']} m")
        lines.append(f"- **Uzunluk L:** {r['L']} m")
        lines.append(f"- **Yükseklik h:** {r['h']} m")
        lines.append(f"- **Cₑ:** {r['ce']}")
        lines.append(f"- **Cₜ:** {r['ct']}")
        lines.append(f"- **sₖ:** {r['sk']:.3f} kN/m²")
        lines.append("")
        lines.append("## 4. Şekil Katsayıları")
        for k, v in r["mu_values"].items():
            lines.append(f"- **{k}:** {v}")
        lines.append("")
        lines.append("## 5. Yük Durumları")
        lines.append("| Yük durumu | μ | Cₑ | Cₜ | sₖ / sAd | Sonuç s (kN/m²) | Referans |")
        lines.append("|---|---:|---:|---:|---:|---:|---|")
        for row in r["rows"]:
            lines.append(f"| {row[0]} | {row[1]:.3f} | {row[2]:.3f} | {row[3]:.3f} | {row[4]:.3f} | {row[5]:.3f} | {row[6]} |")
        lines.append("")
        lines.append("## 6. Kritik Sonuç")
        lines.append(f"- **Kritik yük durumu:** {r['critical_case']}")
        lines.append(f"- **Kritik şekil katsayısı:** {r['critical_mu']:.3f}")
        lines.append(f"- **Kritik tasarım kar yükü:** {r['critical_s']:.3f} kN/m²")
        if r.get("overhang"):
            lines.append(f"- **Çatı kenarı kar sarkıntısı Se:** {r['overhang']['Se']:.3f} kN/m")
        if r["notes"]:
            lines.append("")
            lines.append("## 7. Notlar")
            for n in r["notes"]:
                lines.append(f"- {n}")
        lines.append("")
        lines.append("> Bu çıktı, hızlı mühendislik değerlendirmesi için hazırlanmıştır. Nihai projede ulusal ek, proje özel şartları ve gerektiğinde ilave yük düzenlemeleri ayrıca kontrol edilmelidir.")
        return "\n".join(lines)

    def export_markdown(self):
        if not self.results:
            messagebox.showinfo("Bilgi", "Önce hesap yapınız.")
            return
        path = filedialog.asksaveasfilename(
            title="Markdown raporu kaydet",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Tüm dosyalar", "*.*")]
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.md_report_cache or self.generate_markdown())
        messagebox.showinfo("Tamam", f"Markdown raporu kaydedildi:\n{path}")

    def export_pdf(self):
        if not self.results:
            messagebox.showinfo("Bilgi", "Önce hesap yapınız.")
            return
        if not REPORTLAB_OK:
            messagebox.showerror("Eksik Paket", "PDF için reportlab paketi gerekli.")
            return
        path = filedialog.asksaveasfilename(
            title="PDF raporu kaydet",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")]
        )
        if not path:
            return

        r = self.results
        doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=16*mm, bottomMargin=16*mm)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="MTitle", fontName="Helvetica-Bold", fontSize=18, textColor=colors.HexColor(PRIMARY), spaceAfter=8))
        styles.add(ParagraphStyle(name="MHead", fontName="Helvetica-Bold", fontSize=11, textColor=colors.HexColor(TEXT), spaceBefore=10, spaceAfter=4))
        styles.add(ParagraphStyle(name="BodyTR", fontName="Helvetica", fontSize=9.5, leading=13))
        story = []

        logo = resource_path("assets/mbc_logo.png")
        if os.path.exists(logo):
            story.append(Image(logo, width=135*mm, height=46*mm))
            story.append(Spacer(1, 4*mm))

        story.append(Paragraph(r["project_name"], styles["MTitle"]))
        story.append(Paragraph(f"Hazırlayan: {r['engineer_name']} &nbsp;&nbsp;&nbsp; Tarih: {r['generated_at']}", styles["BodyTR"]))
        if r["client_name"]:
            story.append(Paragraph(f"Müşteri: {r['client_name']}", styles["BodyTR"]))

        story.append(Paragraph("1. Girdiler", styles["MHead"]))
        body = [
            ["Lokasyon", f"{r['city']} / {r['district']}"],
            ["Kar bölgesi", r["region"]],
            ["Rakım", f"{r['altitude']:.1f} m"],
            ["Çatı tipi", r["roof"]],
            ["Cₑ", f"{r['ce']:.3f}"],
            ["Cₜ", f"{r['ct']:.3f}"],
            ["sₖ", f"{r['sk']:.3f} kN/m²"],
            ["sₖ kaynağı", r["sk_source"]],
        ]
        t = Table(body, colWidths=[38*mm, 130*mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#CBD5E1")),
            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
            ("FONTNAME", (0,0), (0,-1), "Helvetica-Bold"),
            ("PADDING", (0,0), (-1,-1), 5),
        ]))
        story.append(t)

        story.append(Paragraph("2. Yük Durumları", styles["MHead"]))
        rows = [["Yük durumu","μ","Cₑ","Cₜ","sₖ/sAd","s (kN/m²)","Referans"]]
        for row in r["rows"]:
            rows.append([row[0], f"{row[1]:.3f}", f"{row[2]:.3f}", f"{row[3]:.3f}", f"{row[4]:.3f}", f"{row[5]:.3f}", row[6]])
        t2 = Table(rows, colWidths=[34*mm, 16*mm, 16*mm, 16*mm, 22*mm, 22*mm, 54*mm])
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#E8F1FB")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.HexColor(TEXT)),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#CBD5E1")),
            ("FONTSIZE", (0,0), (-1,-1), 8.5),
            ("PADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(t2)

        story.append(Paragraph("3. Kritik Sonuç", styles["MHead"]))
        story.append(Paragraph(f"Kritik yük durumu: <b>{r['critical_case']}</b>", styles["BodyTR"]))
        story.append(Paragraph(f"Kritik tasarım kar yükü: <b>{r['critical_s']:.3f} kN/m²</b>", styles["BodyTR"]))
        if r.get("overhang"):
            story.append(Paragraph(f"Çatı kenarı sarkıntısı Se: <b>{r['overhang']['Se']:.3f} kN/m</b>", styles["BodyTR"]))
        if r["notes"]:
            story.append(Paragraph("4. Notlar", styles["MHead"]))
            for note in r["notes"]:
                story.append(Paragraph("• " + note, styles["BodyTR"]))

        story.append(Spacer(1, 8*mm))
        story.append(Paragraph("Bu rapor hızlı mühendislik değerlendirmesi amacıyla oluşturulmuştur. Nihai projede proje özel şartları ayrıca doğrulanmalıdır.", styles["BodyTR"]))

        doc.build(story)
        messagebox.showinfo("Tamam", f"PDF raporu kaydedildi:\n{path}")

    def reset_form(self):
        self.vars["project_name"].set("Kar Yükü Çalışması")
        self.vars["client_name"].set("")
        self.vars["engineer_name"].set("MBÇ Mühendislik")
        self.vars["altitude"].set("0")
        self.vars["manual_sk"].set("")
        self.vars["roof_type"].set("Tek eğimli")
        self.vars["alpha"].set("20")
        self.vars["alpha2"].set("20")
        self.vars["beta"].set("40")
        self.vars["span_b"].set("12")
        self.vars["length_l"].set("24")
        self.vars["height_h"].set("2")
        self.vars["b1"].set("6")
        self.vars["b2"].set("8")
        self.vars["topography"].set("Normal")
        self.vars["ce"].set("1.0")
        self.vars["thermal_desc"].set("Standart")
        self.vars["ct"].set("1.0")
        self.vars["parapet"].set(False)
        self.vars["parapet_h"].set("0.0")
        self.vars["snow_guard"].set(False)
        self.vars["obstacle"].set(False)
        self.vars["obstacle_h"].set("0.5")
        self.vars["exceptional"].set(False)
        self.vars["cesi"].set("2.0")
        self.vars["edge_overhang"].set(False)
        self.vars["snow_depth_d"].set("0.3")
        self.on_roof_type_change()
        self.results = {}
        self.md_report_cache = ""
        self.report_text.delete("1.0", "end")
        for item in self.tree.get_children():
            self.tree.delete(item)
        for card in self.summary_cards:
            card.config(text="—")
        self.draw_diagram()

def main():
    root = tk.Tk()
    app = SnowApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
