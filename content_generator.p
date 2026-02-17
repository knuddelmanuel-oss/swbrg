# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox
import random
from PIL import Image, ImageDraw, ImageFont, ImageTk
import os
import sys

# --- KONFIGURATION & SETUP ---
BASE_DIR = os.path.join(os.path.expanduser("~/Desktop/Project Content Creator"), "Content_Creator_Files")
FINAL_IMAGE_DIR = os.path.join(os.path.expanduser("~/Desktop/Project Content Creator"), "Content")
CATEGORIES = {
    "Weisheiten für's Herz": "weisheiten.txt",
    "Liebessprüche": "liebessprueche.txt",
    "Community Umfragen": "umfragen.txt",
    "Gewusst?": "gewusst.txt",
    "Aktuelle Ereignisse": "ereignisse.txt",
    "Geschichten": "geschichten.txt",
    "Narzissmus": "narzissmus.txt",
    "Dein Sternzeichen": "sternzeichen.txt",
    "Krasser Strass": "frech.txt",
    "Miststück aus Prinzip": "frech.txt",
    "Zieh ab, Arschloch": "frech.txt"
}
CONTENT_LIBRARY = {}

# Mac-Standardpfade plus Fallbacks für Fonts
FONT_MAP = {
    "Helvetica": "/System/Library/Fonts/Helvetica.ttc",
    "Arial": "/System/Library/Fonts/Supplemental/Arial.ttf",
    "Impact": "/System/Library/Fonts/Supplemental/Impact.ttf"
}

def get_font(font_name, size):
    path = FONT_MAP.get(font_name)
    try:
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size=size)
        else:
            # Fallback
            return ImageFont.load_default()
    except Exception as e:
        print(f"Font-Fehler: {e}", file=sys.stderr)
        return ImageFont.load_default()

def setup_directories():
    os.makedirs(BASE_DIR, exist_ok=True)
    os.makedirs(FINAL_IMAGE_DIR, exist_ok=True)
    for name, file in CATEGORIES.items():
        path = os.path.join(BASE_DIR, file)
        if not os.path.exists(path):
            open(path, 'a', encoding='utf-8').close()
        with open(path, 'r', encoding='utf-8') as f:
            CONTENT_LIBRARY[name] = list(dict.fromkeys([line.strip() for line in f if line.strip()]))

def get_background_color_and_font(category):
    # Prüfe exakt auf Kategorie (case sensitive)
    if category == "Krasser Strass":
        return "#FF8C00", "white", "Impact"
    elif category == "Weisheiten für's Herz":
        return "#FAFAD2", "black", "Helvetica"
    elif category == "Miststück aus Prinzip":
        return "#F4A460", "black", "Helvetica"
    elif category == "Zieh ab, Arschloch":
        return "#FF69B4", "white", "Impact"
    else:
        # Standard: dunkel, weiß, Arial
        return "#1E1E1E", "white", "Arial"

def get_watermark_text(category):
    # Wichtig: exakt der Kategoriename!
    if category == "Narzissmus":
        return "Isaak Öztürk"
    elif category == "Dein Sternzeichen":
        return "Dein Sternzeichen"
    elif category in ["Krasser Strass", "Miststück aus Prinzip", "Zieh ab, Arschloch"]:
        return category
    else:
        return "Herzwelt"

def draw_text_centered(draw, text, font, fill, width=1080, height=1350):
    top_margin = 113  # ca. 3cm bei 96dpi
    side_margin = 57  # ca. 1,5cm
    bottom_limit = height // 2

    max_width = width - 2 * side_margin
    words = text.split()
    lines = []
    line = ""

    for word in words:
        test_line = f"{line} {word}".strip()
        if draw.textlength(test_line, font=font) <= max_width:
            line = test_line
        else:
            lines.append(line)
            line = word
    lines.append(line)

    line_height = font.getbbox("A")[3] + 15
    total_text_height = len(lines) * line_height

    available_height = bottom_limit - top_margin
    y_start = top_margin + max(0, (available_height - total_text_height) / 2)

    y = y_start
    for line in lines:
        w = draw.textlength(line, font=font)
        x = (width - w) / 2
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height

def create_image(category, text):
    bg_color, text_color, font_name = get_background_color_and_font(category)
    img = Image.new("RGB", (1080, 1350), bg_color)
    draw = ImageDraw.Draw(img)

    # Große Schrift für Sprüche
    font = get_font(font_name, 95)
    draw_text_centered(draw, text, font, text_color, width=1080, height=1350)

    # Wasserzeichen mittig, 2,5cm Abstand zum unteren Rand (~95px)
    watermark = get_watermark_text(category)
    watermark_font = get_font(font_name, 55)
    w = draw.textlength(watermark, font=watermark_font)
    x = (1080 - w) / 2
    y = 1350 - 95 - watermark_font.getbbox(watermark)[3]
    draw.text((x, y), watermark, font=watermark_font, fill=text_color)

    return img

def main():
    setup_directories()
    root = tk.Tk()
    root.title("Content Creator")
    root.geometry("1150x750")
    root.configure(bg="#1E1E1E")

    style = ttk.Style()
    style.theme_use('default')
    style.configure("TLabel", background="#1E1E1E", foreground="white")
    style.configure("TButton", background="#444", foreground="white")

    category_var = tk.StringVar()
    text_var = tk.StringVar()

    ttk.Label(root, text="Kategorie auswählen:").pack(pady=(10,0))

    button_frame = ttk.Frame(root)
    button_frame.pack(pady=10, padx=10, fill="x")

    categories = list(CATEGORIES.keys())
    rows = 2
    cols = (len(categories) + rows - 1) // rows
    buttons = []

    def load_random_text(cat):
        if cat in CONTENT_LIBRARY:
            texts = CONTENT_LIBRARY[cat]
            if texts:
                text_var.set(random.choice(texts))
                update_preview()
            else:
                text_var.set("(Keine Texte vorhanden)")

    for r in range(rows):
        for c in range(cols):
            idx = r * cols + c
            if idx >= len(categories):
                break
            cat = categories[idx]
            btn = ttk.Button(button_frame, text=cat, command=lambda c=cat: load_random_text(c))
            btn.grid(row=r, column=c, padx=5, pady=5, sticky="ew")
            buttons.append(btn)
        button_frame.grid_columnconfigure(c, weight=1)

    preview_label = tk.Label(root, bg="#1E1E1E")
    preview_label.pack(pady=10, padx=10)

    ttk.Label(root, text="Text anzeigen: (automatisch eingefügt)").pack()
    entry = tk.Entry(root, textvariable=text_var, font=("Helvetica", 13))
    entry.pack(fill="x", padx=10, pady=(0,10))

    def update_preview():
        txt = text_var.get()
        if not txt:
            return
        cat = None
        for btn in buttons:
            if txt in CONTENT_LIBRARY.get(btn['text'], []):
                cat = btn['text']
                break
        if not cat:
            cat = categories[0] if categories else None
        if not cat:
            return
        img = create_image(cat, txt)
        img.thumbnail((280, 350))
        tk_img = ImageTk.PhotoImage(img)
        preview_label.config(image=tk_img)
        preview_label.image = tk_img

    def save():
        txt = text_var.get()
        if not txt:
            messagebox.showwarning("Fehlt", "Text eingeben")
            return
        cat = None
        for btn in buttons:
            if txt in CONTENT_LIBRARY.get(btn['text'], []):
                cat = btn['text']
                break
        if not cat:
            cat = categories[0] if categories else None
        if not cat:
            messagebox.showwarning("Fehlt", "Kategorie wählen")
            return
        img = create_image(cat, txt)
        path = os.path.join(FINAL_IMAGE_DIR, cat)
        os.makedirs(path, exist_ok=True)
        filename = f"{cat.replace(' ', '_')}_{random.randint(1000,9999)}.png"
        img.save(os.path.join(path, filename))
        messagebox.showinfo("Gespeichert", f"Bild gespeichert als {filename}")

    ttk.Button(root, text="Nächster zufälliger Spruch", command=lambda: load_random_text(category_var.get() if category_var.get() else categories[0])).pack(pady=5, fill="x", padx=20)
    ttk.Button(root, text="Bild erstellen & speichern", command=save).pack(pady=5, fill="x", padx=20)

    if categories:
        load_random_text(categories[0])

    root.mainloop()

if __name__ == '__main__':
    main()

