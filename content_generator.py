# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser, filedialog, simpledialog
import random
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageFilter, ImageEnhance, ImageOps
import os
import time
import json
import sys
from pathlib import Path
import re
import requests
from bs4 import BeautifulSoup
import threading
import shutil
import zipfile
import hashlib
from difflib import SequenceMatcher

# --- TESSERACT SUCHE ---
try:
    import pytesseract
    possible_paths = [
        '/opt/homebrew/bin/tesseract',
        '/usr/local/bin/tesseract',
        '/usr/bin/tesseract'
    ]
    tesseract_found = False
    for path in possible_paths:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            tesseract_found = True
            break
except ImportError:
    pytesseract = None

try:
    import pyperclip
except ImportError:
    pyperclip = None


# --- TEXT CLEANER ---
class TextCleaner:
    @staticmethod
    def clean(text):
        if not text:
            return ""
        text = re.sub(r'https?://\S+|www\.\S+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'@[\w\.]+', '', text)
        bad_phrases = [
            r'facebook\.com/\w+', r'instagram\.com/\w+', r'twitter\.com/\w+',
            r'folge uns', r'folgt uns', r'markiere jemanden', r'markiere einen freund',
            r'like für mehr', r'abonniere', r'singlefakten', r'faktastisch',
            r'made with', r'erstellt mit', r'hochgeladen von', r'quelle:',
            r'pic\.', r'\.de', r'\.com', r'\.net'
        ]
        for p in bad_phrases:
            text = re.sub(p, '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text).strip()
        return text


# --- DATENMANAGEMENT ---
class DataManager:
    def __init__(self):
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            self.bundle_dir = Path(sys._MEIPASS)
        else:
            self.bundle_dir = Path(__file__).parent.absolute()

        os.chdir(self.bundle_dir)
        config_path = self.bundle_dir / 'config.json'
        self.config = self._load_json(config_path)

        if not self.config:
            self.config = {
                "DIR_NAMES": {
                    "FONTS_DIR": "fonts",
                    "BASE_DIR": "ContentCreator_Data",
                    "FINAL_IMAGE_DIR": "Fertige_Posts"
                },
                "CATEGORIES_TO_FILES": {
                    "Motivation": "motivation.txt",
                    "Zieh ab, Arschloch": "zieh_ab.txt",
                    "Krasser Strass": "krasser_strass.txt",
                    "Miststück aus Prinzip": "miststueck.txt",
                    "Dein Sternzeichen": "sternzeichen.txt",
                    "Narzissmus": "narzissmus.txt",
                    "Umfragen": "umfragen.txt",
                    "Herzwelt": "herzwelt.txt"
                },
                "COLOR_CONFIG": {
                    "default": {
                        "bg": "#000000",
                        "text_color": "#FFFFFF"
                    }
                },
                "FONT_CONFIG": {
                    "MAP": {},
                    "NAME_MAP": {}
                },
                "SETTINGS": {
                    "IMAGE_SIZE": [1080, 1350],
                    "LOCK_DURATION_MINUTES": 10,
                    "CLEANUP_DURATION_MINUTES": 60
                },
                "LOGO_PATH": "",
                "WEB_SCRAPER": {}
            }

        self.fonts_dir = self.bundle_dir / self.config['DIR_NAMES']['FONTS_DIR']
        self.desktop_path = Path.home() / "Desktop"
        self.base_dir = self.desktop_path / self.config['DIR_NAMES']['BASE_DIR']
        self.final_image_dir = self.desktop_path / self.config['DIR_NAMES']['FINAL_IMAGE_DIR']
        self.used_texts_file = self.base_dir / "used_texts_global.json"

        self.setup_directories()
        self.content_library = self._load_content_library()
        self.used_texts = self._load_json(self.used_texts_file, default={})
        self.clean_old_texts()
        # Alte Auto-Löschung deaktiviert, Rotation übernimmt
        # self.delete_final_images()
        self.scraper_config = self.config.get('WEB_SCRAPER', {})

    def _get_sanitized_category_name(self, category_name):
        return (category_name.lower()
                .replace(' ', '_')
                .replace('ä', 'ae')
                .replace('ö', 'oe')
                .replace('ü', 'ue')
                .replace("'", "")
                .replace(",", ""))

    def get_background_folder_path(self, category):
        return self.base_dir / f"{self._get_sanitized_category_name(category)}_backgrounds"

    def get_final_image_save_path(self, category):
        cat_folder = self.final_image_dir / self._get_sanitized_category_name(category)
        cat_folder.mkdir(exist_ok=True)
        return cat_folder / f"Finales_Bild_{int(time.time())}_{random.randint(100,999)}.png"

    def _load_json(self, path, default=None):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return default

    def save_config(self):
        try:
            with open(self.bundle_dir / 'config.json', 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except:
            pass

    def save_used_texts(self):
        with open(self.used_texts_file, 'w', encoding='utf-8') as f:
            json.dump(self.used_texts, f, indent=4)

    def setup_directories(self):
        self.base_dir.mkdir(exist_ok=True)
        self.final_image_dir.mkdir(exist_ok=True)
        self.fonts_dir.mkdir(exist_ok=True)
        for cat in self.config['CATEGORIES_TO_FILES']:
            self.get_background_folder_path(cat).mkdir(exist_ok=True)

    def _load_content_library(self):
        library = {}
        for filename in set(self.config['CATEGORIES_TO_FILES'].values()):
            path = self.base_dir / filename
            if not path.exists():
                path.touch()
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                with open(path, 'r', encoding='latin-1') as f:
                    lines = f.readlines()
            library[filename] = list(dict.fromkeys([l.strip() for l in lines if l.strip()]))
        return library

    def reload_content_library(self):
        self.content_library = self._load_content_library()

    def clean_old_texts(self):
        now = time.time()
        lock = self.config.get('SETTINGS', {}).get('LOCK_DURATION_MINUTES', 10) * 60
        valid = {t: ts for t, ts in self.used_texts.items() if (now - ts) < lock}
        if len(valid) != len(self.used_texts):
            self.used_texts = valid
            self.save_used_texts()

    def delete_final_images(self):
        limit = self.config.get('SETTINGS', {}).get('CLEANUP_DURATION_MINUTES', 60) * 60
        for r, d, f in os.walk(self.final_image_dir):
            for file in f:
                if file.endswith(('.png', '.jpg')):
                    try:
                        if (time.time() - os.path.getmtime(Path(r) / file)) > limit:
                            os.remove(Path(r) / file)
                    except:
                        pass

    def get_texts_from_source(self, category):
        src = self.config['CATEGORIES_TO_FILES'].get(category)
        local = self.content_library.get(src, [])
        urls = self.scraper_config.get('URLS', {}).get(category)
        if urls:
            try:
                new = WebScraper(self.scraper_config).fetch_texts(urls)
                if new:
                    local.extend(new)
                    local = list(dict.fromkeys(local))
                    with open(self.base_dir / src, 'w', encoding='utf-8') as f:
                        for t in local:
                            f.write(t + '\n')
                    self.reload_content_library()
            except:
                pass
        return local

    def delete_used_text(self, text):
        for fname, texts in self.content_library.items():
            if text in texts:
                self.content_library[fname].remove(text)
                with open(self.base_dir / fname, 'w', encoding='utf-8') as f:
                    for t in self.content_library[fname]:
                        f.write(t + '\n')
                if text in self.used_texts:
                    del self.used_texts[text]
                    self.save_used_texts()
                return True
        return False

    def add_new_category(self, name):
        if name in self.config['CATEGORIES_TO_FILES']:
            return False, "Existiert bereits."
        sanitized = self._get_sanitized_category_name(name)
        fname = f"{sanitized}_sprueche.txt"
        self.config['CATEGORIES_TO_FILES'][name] = fname
        self.config['COLOR_CONFIG'][name] = self.config['COLOR_CONFIG']['default'].copy()
        self.save_config()
        self.setup_directories()
        (self.base_dir / fname).touch()
        self.reload_content_library()
        return True, "Kategorie erstellt."

    def import_backgrounds(self, category, paths):
        target = self.get_background_folder_path(category)
        c = 0
        for p in paths:
            try:
                shutil.copy2(p, target)
                c += 1
            except:
                pass
        return c

    def import_font(self, path):
        try:
            shutil.copy2(path, self.fonts_dir)
            return True
        except:
            return False

    def set_logo(self, path):
        self.config['LOGO_PATH'] = path
        self.save_config()


# --- OCR ---
class OCRProcessor:
    @staticmethod
    def process_image(path):
        if not pytesseract:
            return None, "Tesseract Modul fehlt."
        try:
            img = Image.open(path).convert('L')
            img = ImageEnhance.Contrast(img).enhance(2)
            try:
                txt = pytesseract.image_to_string(img, lang='deu+eng')
            except:
                txt = pytesseract.image_to_string(img, lang='eng')
            if not txt.strip():
                return None, "Kein Text erkannt."
            clean_txt = TextCleaner.clean(OCRProcessor.clean_text(txt))
            return clean_txt, None
        except Exception as e:
            return None, f"Fehler: {e}"

    @staticmethod
    def clean_text(txt):
        txt = txt.replace('Ã¤', 'ä').replace('Ã¶', 'ö').replace('Ã¼', 'ü').replace('ÃŸ', 'ß')
        txt = txt.replace('\n\n', '§P§').replace('\n', ' ').replace('§P§', '\n\n')
        txt = re.sub(r'\s+', ' ', txt)
        txt = re.sub(r'([a-zäöüß])([A-ZÄÖÜ])', r'\1 \2', txt)
        return txt.replace('|', 'I').strip()


# --- BILDGENERATOR ---
class ImageGenerator:
    def __init__(self, data_manager):
        self.dm = data_manager
        self.config = data_manager.config
        self.image_size = (1080, 1350)

    def get_font(self, font_name, size):
        if not font_name:
            font_name = "Helvetica"
        candidates = [
            self.dm.fonts_dir / font_name,
            self.dm.fonts_dir / f"{font_name}.ttf",
            self.dm.fonts_dir / f"{font_name}.otf",
            Path("/Library/Fonts") / f"{font_name}.ttf",
            Path("/Library/Fonts") / f"{font_name}.ttc",
            Path("/System/Library/Fonts") / f"{font_name}.ttc",
            Path("/System/Library/Fonts/Supplemental") / f"{font_name}.ttf"
        ]
        for path in candidates:
            if path.exists():
                try:
                    return ImageFont.truetype(str(path), size=size)
                except:
                    continue
        try:
            return ImageFont.truetype(font_name, size=size)
        except:
            pass
        try:
            return ImageFont.truetype("Arial", size=size)
        except:
            return ImageFont.load_default()

    def calculate_auto_color(self, image):
        if not image:
            return "#FFFFFF"
        thumb = image.resize((1, 1))
        color = thumb.getpixel((0, 0))
        if isinstance(color, int):
            brightness = color
        else:
            r, g, b = color[:3]
            brightness = (r * 299 + g * 587 + b * 114) / 1000
        return "#FFFFFF" if brightness < 120 else "#000000"

    def prepare_background(self, img_source):
        target_w, target_h = self.image_size
        if not img_source:
            return Image.new("RGB", self.image_size, "#000000")
        img_ratio = img_source.width / img_source.height
        target_ratio = target_w / target_h
        if img_ratio > target_ratio:
            new_height = target_h
            new_width = int(new_height * img_ratio)
        else:
            new_width = target_w
            new_height = int(new_width / img_ratio)
        img_resized = img_source.resize((new_width, new_height), Image.Resampling.LANCZOS)
        left = (new_width - target_w) / 2
        top = (new_height - target_h) / 2
        right = (new_width + target_w) / 2
        bottom = (new_height + target_h) / 2
        return img_resized.crop((left, top, right, bottom))

    def wrap_text(self, text, font, max_width, draw):
        lines, words, current_line = [], text.split(), ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        return lines

    def create_image(self, category, headline, body, ui_options):
        if category in ["Krasser Strass", "Miststück aus Prinzip", "Zieh ab, Arschloch"]:
            self.image_size = (960, 960)
        else:
            self.image_size = (1080, 1350)

        bg_config = self.config['COLOR_CONFIG'].get(category, self.config['COLOR_CONFIG']['default'])
        raw_bg = ui_options.get('loaded_background')

        if not raw_bg:
            img = Image.new("RGB", self.image_size, bg_config['bg'])
        else:
            img = self.prepare_background(raw_bg)

        if ui_options.get('bw_filter', False):
            img = ImageOps.grayscale(img).convert("RGB")
            img = ImageEnhance.Contrast(img).enhance(1.2)

        if ui_options.get('blur', 0) > 0:
            img = img.filter(ImageFilter.GaussianBlur(radius=ui_options.get('blur', 0)))

        if ui_options.get('vignette', False):
            overlay = Image.new("RGBA", self.image_size, (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay)
            draw_overlay.rectangle([(0, 0), self.image_size], fill=(0, 0, 0, 100))
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

        draw = ImageDraw.Draw(img)

        if ui_options.get('custom_color'):
            text_color = ui_options['custom_color']
        else:
            text_color = self.calculate_auto_color(img)

        stroke_color = "#000000" if text_color == "#FFFFFF" else "#FFFFFF"

        base_size = 90 if category in ["Zieh ab, Arschloch", "Krasser Strass"] else 60
        scale = ui_options.get('scale', 1.0)

        font_head = self.get_font(ui_options.get('font_name'), int(base_size * scale * 1.3))
        font_body = self.get_font(ui_options.get('font_name'), int(base_size * scale))

        if category in ["Zieh ab, Arschloch", "Krasser Strass"]:
            headline = headline.upper()
            body = body.upper()

        margin_px = 120
        max_width = self.image_size[0] - (2 * margin_px)

        lines_head = self.wrap_text(headline, font_head, max_width, draw) if headline else []
        lines_body = self.wrap_text(body, font_body, max_width, draw) if body else []

        h_head = sum([draw.textbbox((0, 0), l, font=font_head)[3] - draw.textbbox((0, 0), l, font=font_head)[1] for l in lines_head])
        h_body = sum([draw.textbbox((0, 0), l, font=font_body)[3] - draw.textbbox((0, 0), l, font=font_body)[1] for l in lines_body])

        line_spacing = 10
        block_spacing = 40

        total_content_height = 0
        if lines_head:
            total_content_height += h_head + (len(lines_head) - 1) * line_spacing
        if lines_body:
            total_content_height += h_body + (len(lines_body) - 1) * line_spacing
        if lines_head and lines_body:
            total_content_height += block_spacing

        current_y = (self.image_size[1] - total_content_height) * ui_options.get('pos_y', 0.5)

        stroke = int(ui_options.get('stroke', 0))
        use_shadow = ui_options.get('shadow', True)

        if use_shadow:
            shadow_layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
            draw_shadow = ImageDraw.Draw(shadow_layer)

            if text_color.startswith("#"):
                h = text_color.lstrip('#')
                rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            else:
                rgb = (255, 255, 255)

            brightness = (rgb[0] * 299 + rgb[1] * 587 + rgb[2] * 114) / 1000

            if brightness > 128:
                shadow_rgba = (0, 0, 0, 200)
            else:
                shadow_rgba = (255, 255, 255, 180)

            def draw_on_layer(lines, font, start_y, layer_draw):
                y = start_y
                for l in lines:
                    bbox = draw.textbbox((0, 0), l, font=font)
                    w = bbox[2] - bbox[0]
                    h = bbox[3] - bbox[1]
                    avail = self.image_size[0] - w - (2 * margin_px)
                    x = margin_px + (avail * ui_options.get('pos_x', 0.5))
                    layer_draw.text((x, y), l, font=font, fill=shadow_rgba)
                    y += h + line_spacing
                return y

            sy = current_y
            sy = draw_on_layer(lines_head, font_head, sy, draw_shadow)
            if lines_head and lines_body:
                sy += (block_spacing - line_spacing)
            draw_on_layer(lines_body, font_body, sy, draw_shadow)

            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=4))
            img = img.convert("RGBA")
            img = Image.alpha_composite(img, shadow_layer)
            img = img.convert("RGB")
            draw = ImageDraw.Draw(img)

        def draw_main_text(lines, font, start_y):
            y = start_y
            for l in lines:
                bbox = draw.textbbox((0, 0), l, font=font)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
                avail = self.image_size[0] - w - (2 * margin_px)
                x = margin_px + (avail * ui_options.get('pos_x', 0.5))
                draw.text((x, y), l, font=font, fill=text_color,
                          stroke_width=stroke, stroke_fill=stroke_color)
                y += h + line_spacing
            return y

        ty = current_y
        ty = draw_main_text(lines_head, font_head, ty)
        if lines_head and lines_body:
            ty += (block_spacing - line_spacing)
        end_y = draw_main_text(lines_body, font_body, ty)

        if category in ["Narzissmus", "Umfragen", "Herzwelt"]:
            if category == "Narzissmus":
                watermark = "Isaak Öztürk"
            else:
                watermark = "Herzwelt"

            wm_font = self.get_font("Noteworthy", 40)
            wm_bbox = draw.textbbox((0, 0), watermark, font=wm_font)
            wm_w = wm_bbox[2] - wm_bbox[0]
            wm_x = (self.image_size[0] - wm_w) / 2
            wm_y = end_y + 40
            draw.text((wm_x, wm_y), watermark, font=wm_font,
                      fill=text_color, stroke_width=1, stroke_fill=stroke_color)

        logo_path = self.dm.config.get('LOGO_PATH')
        if logo_path and os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path).convert("RGBA")
                target_w = 200
                ratio = target_w / logo.width
                target_h = int(logo.height * ratio)
                logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
                lx = self.image_size[0] - target_w - 50
                ly = self.image_size[1] - target_h - 50
                img.paste(logo, (lx, ly), logo)
            except:
                pass

        return img


# --- WEBSCRAPER ---
class WebScraper:
    def __init__(self, config):
        self.headers = {'User-Agent': config.get('USER_AGENT', 'Mozilla/5.0')}
        self.timeout = 10

    def fetch_texts(self, urls):
        texts = []
        for url in urls:
            try:
                r = requests.get(url, headers=self.headers, timeout=self.timeout)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.content, 'html.parser')
                    texts.extend([d.get_text(strip=True) for d in soup.find_all('div', class_='zitat-text')])
            except:
                pass
        return [self._clean(t) for t in list(set(texts)) if 10 < len(t) < 200]

    def _clean(self, t):
        return re.sub(r'\s+', ' ', t).strip('"\'')


# --- BATCH ---
class BatchGeneratorWindow(tk.Toplevel):
    def __init__(self, parent, data_manager, image_generator, category, ui_options, override_texts=None):
        super().__init__(parent)
        self.dm, self.ig, self.cat, self.opts = data_manager, image_generator, category, ui_options
        self.override_texts = override_texts
        self.items = []
        self.update_timers = {}

        title_txt = f"Batch-Vorschau: {category}"
        if override_texts:
            title_txt += f" (OCR: {len(override_texts)} Texte)"

        self.title(title_txt)
        self.geometry("1500x1000")
        self.state('zoomed')
        self.configure(bg="#121212")

        master = ttk.Frame(self, style="TFrame")
        master.pack(fill="x", pady=8, padx=16)

        ttk.Label(master, text="MASTER CONTROLS:",
                  font=("Arial", 10, "bold"),
                  foreground="#00E5FF",
                  background="#121212").pack(side="left", padx=8)

        ttk.Label(master, text="Größe:",
                  foreground="white", background="#121212").pack(side="left")
        self.master_scale = tk.DoubleVar(value=ui_options.get('scale', 1.0))
        tk.Scale(master, from_=0.5, to=2.5, variable=self.master_scale,
                 orient="horizontal", resolution=0.1,
                 bg="#121212", fg="white",
                 highlightthickness=0, length=120).pack(side="left", padx=4)

        ttk.Button(master, text="⬇ Auf alle anwenden",
                   command=self.apply_master_settings).pack(side="left", padx=8)
        ttk.Button(master, text="💾 Alle als ZIP speichern",
                   command=self.save_zip, style="Accent.TButton").pack(side="right")

        cv = tk.Canvas(self, bg="#121212", highlightthickness=0)
        scr = ttk.Scrollbar(self, orient="vertical", command=cv.yview)
        self.frame = ttk.Frame(cv, style="TFrame")
        self.frame.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.create_window((0, 0), window=self.frame, anchor="nw")
        cv.configure(yscrollcommand=scr.set)
        cv.pack(side="left", fill="both", expand=True)
        scr.pack(side="right", fill="y")

        self.generate_initial()

    def generate_initial(self):
        if self.override_texts:
            quotes = self.override_texts
        else:
            src = self.dm.config['CATEGORIES_TO_FILES'].get(self.cat)
            texts = [t for t in self.dm.content_library.get(src, []) if t not in self.dm.used_texts]
            random.shuffle(texts)
            quotes = texts[:6]

        if not quotes:
            ttk.Label(self.frame, text="Keine Texte verfügbar.", foreground="white").pack(pady=20)
            return

        bg_folder = self.dm.get_background_folder_path(self.cat)
        bgs = list(bg_folder.glob('*.jpg')) + list(bg_folder.glob('*.png'))

        cols = 2

        for i, q in enumerate(quotes):
            row = i // cols
            col = i % cols

            bg_img = None
            if bgs:
                bg_img = Image.open(random.choice(bgs)).convert("RGB")

            local_opts = self.opts.copy()
            local_opts['loaded_background'] = bg_img
            local_opts['custom_color'] = None

            img = self.ig.create_image(self.cat, "", q, local_opts)

            card = tk.Frame(self.frame, bg="#1E1E1E", highlightbackground="#333", highlightthickness=1)
            card.grid(row=row, column=col, padx=12, pady=12, sticky="n")

            thumb = img.copy()
            thumb.thumbnail((300, 375))
            tk_thumb = ImageTk.PhotoImage(thumb)
            lbl = tk.Label(card, image=tk_thumb, bg="#1E1E1E")
            lbl.image = tk_thumb
            lbl.pack(pady=8)

            tk.Label(card, text="Text bearbeiten:", bg="#1E1E1E",
                     fg="#888", font=("Arial", 8)).pack(anchor="w", padx=8)
            txt_w = tk.Text(card, height=4, width=35, font=("Arial", 10),
                            bg="#2b2b2b", fg="white", relief="flat", wrap="word")
            txt_w.insert("1.0", q)
            txt_w.pack(padx=8, pady=(0, 4))
            txt_w.bind("<KeyRelease>", lambda e, idx=i: self.trigger_live_update(idx))

            ctrl_row = tk.Frame(card, bg="#1E1E1E")
            ctrl_row.pack(fill="x", padx=8, pady=4)

            tk.Label(ctrl_row, text="Größe:", bg="#1E1E1E", fg="white").pack(side="left")
            scale_var = tk.DoubleVar(value=local_opts.get('scale', 1.0))
            tk.Scale(ctrl_row, from_=0.5, to=2.5, variable=scale_var,
                     orient="horizontal", resolution=0.1,
                     bg="#1E1E1E", fg="white",
                     highlightthickness=0, length=120,
                     command=lambda v, idx=i: self.trigger_live_update(idx)).pack(side="left", padx=4)

            if pyperclip:
                ttk.Button(ctrl_row, text="Kopieren", width=8,
                           command=lambda w=txt_w: pyperclip.copy(w.get("1.0", "end-1c"))).pack(side="right")

            self.items.append({
                "txt_w": txt_w,
                "lbl": lbl,
                "scale": scale_var,
                "bg": bg_img,
                "img": img
            })

    def apply_master_settings(self):
        val = self.master_scale.get()
        for idx, item in enumerate(self.items):
            item["scale"].set(val)
            self.trigger_live_update(idx)

    def trigger_live_update(self, idx):
        if idx in self.update_timers:
            self.after_cancel(self.update_timers[idx])
        self.update_timers[idx] = self.after(800, lambda: self.perform_update(idx))

    def perform_update(self, idx):
        item = self.items[idx]
        new_text = item["txt_w"].get("1.0", "end-1c").strip()
        new_scale = item["scale"].get()

        local_opts = self.opts.copy()
        local_opts['scale'] = new_scale
        local_opts['loaded_background'] = item["bg"]
        local_opts['custom_color'] = None

        new_img = self.ig.create_image(self.cat, "", new_text, local_opts)

        thumb = new_img.copy()
        thumb.thumbnail((300, 375))
        tk_thumb = ImageTk.PhotoImage(thumb)
        item["lbl"].configure(image=tk_thumb)
        item["lbl"].image = tk_thumb
        item["img"] = new_img

    def save_zip(self):
        if not self.items:
            return
        fname = filedialog.asksaveasfilename(defaultextension=".zip",
                                             filetypes=[("ZIP", "*.zip")])
        if fname:
            with zipfile.ZipFile(fname, 'w') as zf:
                for i, item in enumerate(self.items):
                    import io
                    buf = io.BytesIO()
                    item["img"].save(buf, format='PNG')
                    zf.writestr(f"Post_{i+1}.png", buf.getvalue())
                    q = item["txt_w"].get("1.0", "end-1c").strip()
                    self.dm.used_texts[q] = time.time()
            self.dm.save_used_texts()
            messagebox.showinfo("Erfolg", "ZIP gespeichert.")


# --- APP ---
class ContentCreatorApp(tk.Frame):
    def __init__(self, root, data_manager):
        super().__init__(root)
        self.root = root
        self.dm = data_manager
        self.ig = ImageGenerator(data_manager)
        self.root.title("Content Creator Pro - V22 (Modern + Rotation)")
        self.root.geometry("1400x900")  # etwas niedriger, damit es auf mehr Screens passt
        self.root.configure(bg="#101010")
        self.pack(fill="both", expand=True)

        self.text_scale = tk.DoubleVar(value=1.0)
        self.stroke = tk.DoubleVar(value=0.0)
        self.blur = tk.DoubleVar(value=0.0)
        self.pos_x = tk.DoubleVar(value=0.5)
        self.pos_y = tk.DoubleVar(value=0.5)
        self.show_safe_zone = tk.BooleanVar(value=False)
        self.use_vignette = tk.BooleanVar(value=False)
        self.use_bw = tk.BooleanVar(value=False)
        self.use_shadow = tk.BooleanVar(value=True)
        self.custom_color = None
        self.cat_var = tk.StringVar()
        self.font_var = tk.StringVar()
        self.loaded_bgs = {}
        self.curr_bg = None

        self.setup_ui()
        cats = list(self.dm.config['CATEGORIES_TO_FILES'].keys())
        if cats:
            self.load_cat(cats[0])

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')

        bg_main = "#101010"
        bg_panel = "#181818"
        accent = "#00E5FF"
        accent_secondary = "#FF3B30"

        style.configure("TFrame", background=bg_main)
        style.configure("Card.TFrame", background=bg_panel)
        style.configure("TLabel", background=bg_main, foreground="#FFFFFF")
        style.configure("TopBar.TFrame", background="#151515")
        style.configure("TopBar.TLabel", background="#151515",
                        foreground="#FFFFFF", font=("Segoe UI", 12, "bold"))

        style.configure("TButton",
                        background="#333333",
                        foreground="white",
                        borderwidth=0,
                        focusthickness=0,
                        padding=4)
        style.map("TButton",
                  background=[('active', '#444444')],
                  foreground=[('disabled', '#777777')])

        style.configure("Accent.TButton",
                        background=accent,
                        foreground="#000000",
                        font=("Segoe UI", 9, "bold"),
                        padding=6)
        style.map("Accent.TButton",
                  background=[('active', '#00B8D4')])

        style.configure("Danger.TButton",
                        background=accent_secondary,
                        foreground="#FFFFFF",
                        font=("Segoe UI", 9, "bold"),
                        padding=6)

        style.configure("TCheckbutton", background=bg_panel, foreground="white")
        style.configure("TLabelframe", background=bg_panel, foreground="#AAAAAA")
        style.configure("TLabelframe.Label", background=bg_panel, foreground="#AAAAAA")

        # Top-Bar (wie bisher)
        top_bar = ttk.Frame(self, style="TopBar.TFrame")
        top_bar.pack(fill="x", padx=0, pady=(0, 3))

        ttk.Label(top_bar, text="Content Creator Pro",
                  style="TopBar.TLabel").pack(side="left", padx=12, pady=4)

        ttk.Label(top_bar,
                  text="Canva-Style Dashboard · 25-Tage Rotation aktiv",
                  background="#151515",
                  foreground="#BBBBBB",
                  font=("Segoe UI", 8)).pack(side="right", padx=12)

        container = ttk.Frame(self, style="TFrame")
        container.pack(fill="both", expand=True, padx=6, pady=4)

        # Linke Seite (ohne Scrollbar, aber kompakter)
        left = ttk.Frame(container, width=440, style="Card.TFrame")
        left.pack(side="left", fill="y", padx=(0, 6))
        left.pack_propagate(False)

        right = ttk.Frame(container, style="Card.TFrame")
        right.pack(side="right", fill="both", expand=True)

        # Quick Actions
        tools_frame = ttk.Labelframe(left, text="Quick Actions", style="TLabelframe")
        tools_frame.pack(fill="x", pady=(4, 2), padx=6)

        btn_row = ttk.Frame(tools_frame, style="Card.TFrame")
        btn_row.pack(fill="x", pady=1)

        ttk.Button(btn_row, text="📋 Clipboard",
                   command=self.paste_clip).pack(side="left", fill="x", expand=True, padx=(0, 2))
        ttk.Button(btn_row, text="📷 OCR",
                   command=self.run_ocr).pack(side="left", fill="x", expand=True, padx=(2, 0))

        ttk.Button(tools_frame, text="🔁 6er-Vorschau",
                   command=self.open_batch).pack(fill="x", pady=(2, 1))

        ttk.Checkbutton(tools_frame,
                        text="Safe Zone / Fadenkreuz",
                        variable=self.show_safe_zone,
                        command=self.update_prev).pack(fill="x", pady=2)

        # Layout & Kategorie
        meta_frame = ttk.Labelframe(left, text="Layout & Kategorie", style="TLabelframe")
        meta_frame.pack(fill="x", pady=2, padx=6)

        f_frame = ttk.Frame(meta_frame, style="Card.TFrame")
        f_frame.pack(fill="x", pady=2)
        ttk.Label(f_frame, text="Schriftart:",
                  foreground="white", background=bg_panel).pack(side="left")
        ttk.Button(f_frame, text="+", width=3,
                   command=self.import_font).pack(side="right")
        self.font_cb = ttk.Combobox(meta_frame, textvariable=self.font_var,
                                    state="readonly", values=self.get_font_list())
        self.font_cb.pack(fill="x", pady=(0, 2))
        self.font_cb.bind("<<ComboboxSelected>>", self.update_prev)

        c_frame = ttk.Frame(meta_frame, style="Card.TFrame")
        c_frame.pack(fill="x", pady=1)
        ttk.Label(c_frame, text="Kategorie:",
                  foreground="white", background=bg_panel).pack(side="left")
        ttk.Button(c_frame, text="+ Neu", width=6,
                   command=self.new_cat).pack(side="right")

        self.cat_cont = ttk.Frame(meta_frame, style="Card.TFrame")
        self.cat_cont.pack(fill="x", pady=(1, 2))
        self.refresh_cat_btns()

        # Text-Layer
        text_frame = ttk.Labelframe(left, text="Text-Layer", style="TLabelframe")
        text_frame.pack(fill="x", pady=2, padx=6)

        tk.Label(text_frame, text="Headline (optional):",
                 bg=bg_panel, fg="white",
                 font=("Arial", 9, "bold")).pack(anchor="w", pady=(3, 0), padx=4)
        # Höhe 2 -> 1
        self.txt_head = tk.Text(text_frame, height=1,
                                bg="#333333", fg="white",
                                font=("Arial", 10), relief="flat", wrap="word")
        self.txt_head.pack(fill="x", pady=1, padx=4)
        self.txt_head.bind("<KeyRelease>", self.update_prev)

        tk.Label(text_frame, text="Haupttext:",
                 bg=bg_panel, fg="white",
                 font=("Arial", 9)).pack(anchor="w", pady=(3, 0), padx=4)
        # Höhe 6 -> 5
        self.txt = tk.Text(text_frame, height=5,
                           bg="#252525", fg="white",
                           font=("Arial", 10), relief="flat", wrap="word")
        self.txt.pack(fill="x", pady=1, padx=4)
        self.txt.bind("<KeyRelease>", self.update_prev)

        # Sliders
        sliders_frame = ttk.Labelframe(left, text="Position & Größe", style="TLabelframe")
        sliders_frame.pack(fill="x", pady=2, padx=6)

        c_grid = ttk.Frame(sliders_frame, style="Card.TFrame")
        c_grid.pack(fill="x", pady=1, padx=4)
        self.add_sl(c_grid, "Größe", self.text_scale, 0.5, 2.5, 0)
        self.add_sl(c_grid, "Pos X", self.pos_x, 0.0, 1.0, 1)
        self.add_sl(c_grid, "Pos Y", self.pos_y, 0.0, 1.0, 2)
        self.add_sl(c_grid, "Rand", self.stroke, 0.0, 5.0, 3)
        self.add_sl(c_grid, "Blur", self.blur, 0.0, 20.0, 4)

        # Look & Feel
        lf_frame = ttk.Labelframe(left, text="Look & Feel", style="TLabelframe")
        lf_frame.pack(fill="x", pady=2, padx=6)
        ttk.Checkbutton(lf_frame, text="Soft-Shadow (Auto)",
                        variable=self.use_shadow,
                        command=self.update_prev).pack(anchor="w", padx=4, pady=1)
        ttk.Checkbutton(lf_frame, text="Vignette (Hintergrund)",
                        variable=self.use_vignette,
                        command=self.update_prev).pack(anchor="w", padx=4, pady=1)
        ttk.Checkbutton(lf_frame, text="Schwarz-Weiß (B&W)",
                        variable=self.use_bw,
                        command=self.update_prev).pack(anchor="w", padx=4, pady=1)

        # Farbe & Hintergrund
        act = ttk.Labelframe(left, text="Farbe & Hintergrund", style="TLabelframe")
        act.pack(fill="x", pady=2, padx=6)

        act_row = ttk.Frame(act, style="Card.TFrame")
        act_row.pack(fill="x", pady=1, padx=4)

        ttk.Button(act_row, text="🎨 Textfarbe",
                   command=self.pick_col).pack(side="left", fill="x", expand=True, padx=(0, 2))
        ttk.Button(act_row, text="↺ Auto",
                   command=self.reset_col).pack(side="left", fill="x", expand=True, padx=2)
        ttk.Button(act_row, text="🖼 Hintergrund",
                   command=self.cycle_bg).pack(side="left", fill="x", expand=True, padx=(2, 0))

        ttk.Button(act, text="Hintergründe importieren (+)",
                   command=self.import_bg).pack(fill="x", pady=(2, 2), padx=4)

        # Speichern & sperren – bleibt unten links, aber mit kleineren Abständen
        ttk.Button(left, text="💾 Speichern & sperren (Rotation)",
                   style="Accent.TButton",
                   command=self.save).pack(fill="x", pady=(2, 4), padx=8)

        # Preview rechts
        preview_frame = ttk.Labelframe(right, text="Live-Vorschau", style="TLabelframe")
        preview_frame.pack(fill="both", expand=True, padx=6, pady=6)

        self.prev_lbl = tk.Label(preview_frame, bg="#222222")
        self.prev_lbl.pack(fill="both", expand=True, padx=4, pady=4)
        self.prev_lbl.bind("<Enter>", self.bind_wheel)
        self.prev_lbl.bind("<Leave>", self.unbind_wheel)

    def add_sl(self, p, txt, var, f, t, r):
        ttk.Label(p, text=txt, foreground="white", background="#181818").grid(row=r, column=0, sticky="w")
        tk.Scale(p, from_=f, to=t, variable=var, orient="horizontal",
                 bg="#333333", fg="white", resolution=0.05,
                 highlightthickness=0, command=self.update_prev).grid(row=r, column=1, sticky="ew")
        p.columnconfigure(1, weight=1)

    def run_ocr(self):
        files = filedialog.askopenfilenames(
            title="Bilder auswählen (auch mehrere)",
            filetypes=[("Bilder", "*.png *.jpg *.jpeg")]
        )
        if not files:
            return

        if len(files) == 1:
            self.txt.delete("1.0", tk.END)
            self.txt.insert("1.0", "Lese...")
            self.root.update()
            txt, err = OCRProcessor.process_image(files[0])
            self.txt.delete("1.0", tk.END)
            if err:
                messagebox.showwarning("OCR", err)
            else:
                self.txt.insert("1.0", txt)
                self.update_prev()
                messagebox.showinfo("OCR", "Erfolg!")
        else:
            messagebox.showinfo(
                "OCR Batch",
                f"Starte Texterkennung für {len(files)} Bilder...\n"
                f"Das Fenster öffnet sich gleich automatisch."
            )
            threading.Thread(target=self.process_batch_ocr, args=(files,), daemon=True).start()

    def process_batch_ocr(self, files):
        texts = []
        for f in files:
            t, _ = OCRProcessor.process_image(f)
            if t and len(t) > 5:
                texts.append(t)
        self.root.after(0, lambda: self.finish_batch_ocr(texts))

    def finish_batch_ocr(self, texts):
        if not texts:
            messagebox.showwarning("OCR", "Keine lesbaren Texte gefunden.")
            return
        opts = {
            'scale': self.text_scale.get(),
            'pos_x': self.pos_x.get(),
            'pos_y': self.pos_y.get(),
            'stroke': self.stroke.get(),
            'blur': self.blur.get(),
            'font_name': self.font_var.get(),
            'custom_color': self.custom_color,
            'loaded_background': self.curr_bg,
            'vignette': self.use_vignette.get(),
            'bw_filter': self.use_bw.get(),
            'shadow': self.use_shadow.get()
        }
        BatchGeneratorWindow(self.root, self.dm, self.ig, self.cat_var.get(), opts, override_texts=texts)

    def get_font_list(self):
        local = [f.stem for f in self.dm.fonts_dir.glob("*.*") if f.suffix in ['.ttf', '.otf']]
        system = ["Arial", "Helvetica", "Times New Roman", "Courier New", "Verdana", "Georgia", "Impact"]
        return sorted(list(set(local + system)))

    def refresh_cat_btns(self):
        for w in self.cat_cont.winfo_children():
            w.destroy()
        cats = list(self.dm.config['CATEGORIES_TO_FILES'].keys())
        for i, c in enumerate(cats):
            ttk.Button(self.cat_cont, text=c,
                       command=lambda x=c: self.load_cat(x)).grid(
                           row=i // 3, column=i % 3,
                           sticky="ew", padx=2, pady=2
                       )

    def load_cat(self, cat):
        self.cat_var.set(cat)
        texts = self.dm.get_texts_from_source(cat)
        avail = [t for t in texts if t not in self.dm.used_texts]
        self.txt.delete("1.0", tk.END)
        self.txt_head.delete("1.0", tk.END)
        self.txt.insert("1.0", random.choice(avail) if avail else "Leer")

        self.loaded_bgs[cat] = []
        folder = self.dm.get_background_folder_path(cat)
        for f in list(folder.glob('*.jpg')) + list(folder.glob('*.png')):
            try:
                self.loaded_bgs[cat].append(Image.open(f).convert("RGB"))
            except:
                pass
        self.cycle_bg()

    def cycle_bg(self):
        bgs = self.loaded_bgs.get(self.cat_var.get(), [])
        if bgs:
            self.curr_bg = random.choice(bgs)
        else:
            self.curr_bg = None
        self.update_prev()

    def update_prev(self, _=None):
        cat = self.cat_var.get()
        txt_body = self.txt.get("1.0", "end-1c").strip()
        txt_head = self.txt_head.get("1.0", "end-1c").strip()

        if not cat:
            return

        opts = {
            'scale': self.text_scale.get(),
            'pos_x': self.pos_x.get(),
            'pos_y': self.pos_y.get(),
            'stroke': self.stroke.get(),
            'blur': self.blur.get(),
            'font_name': self.font_var.get(),
            'custom_color': self.custom_color,
            'loaded_background': self.curr_bg,
            'vignette': self.use_vignette.get(),
            'bw_filter': self.use_bw.get(),
            'shadow': self.use_shadow.get()
        }

        img = self.ig.create_image(cat, txt_head, txt_body, opts)
        self.final_img = img

        preview_img = img.copy()
        if self.show_safe_zone.get():
            draw = ImageDraw.Draw(preview_img)
            w, h = self.ig.image_size
            cx, cy = w / 2, h / 2

            draw.line([(cx, 0), (cx, h)], fill="red", width=2)
            draw.line([(0, cy), (w, cy)], fill="red", width=2)

            safe_margin = 120
            safe_bottom = 250
            draw.rectangle([safe_margin, 100, w - safe_margin, h - safe_bottom],
                           outline="cyan", width=3)

        prev = preview_img
        w = self.prev_lbl.winfo_width()
        h = self.prev_lbl.winfo_height()
        if w > 10 and h > 10:
            prev.thumbnail((w - 10, h - 10))
        else:
            prev.thumbnail((600, 800))

        tk_img = ImageTk.PhotoImage(prev)
        self.prev_lbl.config(image=tk_img)
        self.prev_lbl.image = tk_img

    def bind_wheel(self, _):
        self.root.bind_all("<MouseWheel>", self.on_wheel)
        self.root.bind_all("<Button-4>", self.on_wheel)
        self.root.bind_all("<Button-5>", self.on_wheel)

    def unbind_wheel(self, _):
        self.root.unbind_all("<MouseWheel>")
        self.root.unbind_all("<Button-4>")
        self.root.unbind_all("<Button-5>")

    def on_wheel(self, e):
        d = 1 if (getattr(e, "delta", 0) > 0 or getattr(e, "num", 0) == 4) else -1
        self.text_scale.set(max(0.5, min(3.0, self.text_scale.get() + d * 0.05)))
        self.update_prev()

    def new_cat(self):
        n = simpledialog.askstring("Neu", "Name:")
        if n:
            ok, msg = self.dm.add_new_category(n)
            if ok:
                self.refresh_cat_btns()
            else:
                messagebox.showwarning("Fehler", msg)

    def import_bg(self):
        files = filedialog.askopenfilenames(filetypes=[("Bilder", "*.jpg *.png")])
        if files and self.cat_var.get():
            self.dm.import_backgrounds(self.cat_var.get(), files)
            self.load_cat(self.cat_var.get())

    def import_font(self):
        f = filedialog.askopenfilename(filetypes=[("Fonts", "*.ttf *.otf")])
        if f:
            if self.dm.import_font(f):
                self.font_cb['values'] = self.get_font_list()
                messagebox.showinfo("Info", "Schriftart importiert!")

    def pick_col(self):
        c = colorchooser.askcolor()[1]
        if c:
            self.custom_color = c
            self.update_prev()

    def reset_col(self):
        self.custom_color = None
        self.update_prev()

    def paste_clip(self):
        if not pyperclip:
            messagebox.showwarning("Fehler", "pyperclip nicht installiert.")
            return
        try:
            clip = pyperclip.paste()
            if clip:
                self.txt.delete("1.0", tk.END)
                self.txt.insert("1.0", clip)
                self.update_prev()
        except:
            pass

    def open_batch(self):
        if not self.cat_var.get():
            return
        opts = {
            'scale': self.text_scale.get(),
            'pos_x': self.pos_x.get(),
            'pos_y': self.pos_y.get(),
            'stroke': self.stroke.get(),
            'blur': self.blur.get(),
            'font_name': self.font_var.get(),
            'custom_color': self.custom_color,
            'loaded_background': self.curr_bg,
            'vignette': self.use_vignette.get(),
            'bw_filter': self.use_bw.get(),
            'shadow': self.use_shadow.get()
        }
        BatchGeneratorWindow(self.root, self.dm, self.ig, self.cat_var.get(), opts)

    def save(self):
        if not self.cat_var.get():
            return
        txt = self.txt.get("1.0", "end-1c").strip()
        if not txt:
            messagebox.showwarning("Leer", "Kein Text!")
            return

        # wird unten vom Rotation-System überschrieben (new_save),
        # bleibt aber als Fallback erhalten.
        path = self.dm.get_final_image_save_path(self.cat_var.get())
        self.final_img.save(path, "PNG")
        self.dm.used_texts[txt] = time.time()
        self.dm.save_used_texts()

        current_cat = self.cat_var.get()
        self.load_cat(current_cat)
        messagebox.showinfo("Gespeichert", f"Bild gespeichert!\n{Path(path).name}")



# ==========================================================
# CLEAN 25-DAY ROTATION + GHOST SYSTEM
# ==========================================================
ROTATION_DAYS = 25
ROTATION_SECONDS = ROTATION_DAYS * 24 * 60 * 60

BASE_PATH = Path(__file__).parent
DATA_PATH = BASE_PATH / "rotation_data.json"
ARCHIVE_PATH = BASE_PATH / "rotation_archive"
ARCHIVE_PATH.mkdir(exist_ok=True)

VISIBLE_ROOT = Path.home() / "Desktop" / "ContentCreator_Data" / "Fertige_Posts"
VISIBLE_ROOT.mkdir(parents=True, exist_ok=True)

SESSION_IMAGES = set()


def load_rotation_data():
    if not DATA_PATH.exists():
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump({"texts": {}, "images": {}, "ghost": {}}, f)
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_rotation_data(data):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def text_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def text_blocked(text):
    data = load_rotation_data()
    now = time.time()

    for old_text, ts in data.get("texts", {}).items():
        if now - ts < ROTATION_SECONDS:
            if text_similarity(text, old_text) > 0.80:
                return True
    return False


def lock_text(text):
    data = load_rotation_data()
    if "texts" not in data:
        data["texts"] = {}
    data["texts"][text] = time.time()
    save_rotation_data(data)


def archive_image(path):
    path = Path(path)

    try:
        rel = path.relative_to(VISIBLE_ROOT)
    except ValueError:
        rel = Path(path.name)

    target = ARCHIVE_PATH / rel
    target.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.move(str(path), str(target))
        data = load_rotation_data()
        if "images" not in data:
            data["images"] = {}
        data["images"][str(rel)] = time.time()
        save_rotation_data(data)
    except Exception:
        pass


def release_images(visible_folder):
    visible_folder = Path(visible_folder)
    data = load_rotation_data()
    now = time.time()

    images = data.get("images", {})
    for rel, ts in list(images.items()):
        if now - ts > ROTATION_SECONDS:
            archived = ARCHIVE_PATH / rel
            visible = visible_folder / rel
            try:
                if archived.exists():
                    visible.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(archived), str(visible))
                del images[rel]
            except Exception:
                continue

    data["images"] = images
    save_rotation_data(data)


def ghost_save(category, scale, pos_y):
    data = load_rotation_data()
    if "ghost" not in data:
        data["ghost"] = {}

    if category not in data["ghost"]:
        data["ghost"][category] = {"scale": [], "pos_y": []}

    data["ghost"][category]["scale"].append(float(scale))
    data["ghost"][category]["pos_y"].append(float(pos_y))

    data["ghost"][category]["scale"] = data["ghost"][category]["scale"][-30:]
    data["ghost"][category]["pos_y"] = data["ghost"][category]["pos_y"][-30:]

    save_rotation_data(data)


def ghost_apply(app, category):
    data = load_rotation_data()
    ghost = data.get("ghost", {})
    if category not in ghost:
        return

    g = ghost[category]

    if g.get("scale"):
        avg_scale = sum(g["scale"]) / len(g["scale"])
        app.text_scale.set(avg_scale)

    if g.get("pos_y"):
        avg_pos_y = sum(g["pos_y"]) / len(g["pos_y"])
        app.pos_y.set(avg_pos_y)

    try:
        app.update_prev()
    except Exception:
        pass


_original_save = ContentCreatorApp.save
_original_load_cat = ContentCreatorApp.load_cat
_original_init = ContentCreatorApp.__init__
_original_destroy = ContentCreatorApp.destroy


def new_save(self):
    text = self.txt.get("1.0", "end-1c").strip()

    if not text:
        messagebox.showwarning("Leer", "Kein Text!")
        return

    if text_blocked(text):
        messagebox.showwarning(
            "Blockiert",
            "Text ist noch gesperrt oder zu ähnlich zu einem früheren Post."
        )
        return

    path = self.dm.get_final_image_save_path(self.cat_var.get())
    self.final_img.save(path, "PNG")

    try:
        rel = Path(path).relative_to(VISIBLE_ROOT)
        SESSION_IMAGES.add(str(rel))
    except ValueError:
        SESSION_IMAGES.add(Path(path).name)

    lock_text(text)

    self.dm.used_texts[text] = time.time()
    self.dm.save_used_texts()

    ghost_save(self.cat_var.get(), self.text_scale.get(), self.pos_y.get())

    self.load_cat(self.cat_var.get())
    messagebox.showinfo("Gespeichert", f"Bild gespeichert!\n{Path(path).name}")


ContentCreatorApp.save = new_save


def new_load_cat(self, cat):
    _original_load_cat(self, cat)

    attempts = 0
    while attempts < 20:
        txt = self.txt.get("1.0", "end-1c").strip()
        if not txt or not text_blocked(txt):
            break
        _original_load_cat(self, cat)
        attempts += 1

    ghost_apply(self, cat)


ContentCreatorApp.load_cat = new_load_cat


def new_init(self, root, data_manager):
    _original_init(self, root, data_manager)
    VISIBLE_ROOT.mkdir(parents=True, exist_ok=True)
    release_images(VISIBLE_ROOT)


ContentCreatorApp.__init__ = new_init


def new_destroy(self):
    for rel in SESSION_IMAGES:
        file = VISIBLE_ROOT / rel
        if file.exists():
            archive_image(file)

    _original_destroy(self)


ContentCreatorApp.destroy = new_destroy

print("Stable 25-Day Rotation + Ghost System + Modern UI aktiviert.")


if __name__ == "__main__":
    root = tk.Tk()
    dm = DataManager()
    app = ContentCreatorApp(root, dm)
    root.mainloop()
