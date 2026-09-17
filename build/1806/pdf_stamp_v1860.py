from __future__ import annotations

import base64
import datetime as _dt
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


MODULE_VERSION = "1.8.6"
MARKER = "PZ_PDF_STAMP_TOOL_V1860"
BASE = Path(__file__).resolve().parent

STAMP_FILES = {
    "statik": "Engbers_Statik_Stempel_Unterschrift.png",
    "sasv": "Engbers_saSV_Stempel_Unterschrift.png",
}

LOCAL_STAMP_FILES = {
    "statik": "statik_stempel_unterschrift.png",
    "sasv": "sasv_stempel_unterschrift.png",
}

STAMP_LABELS = {
    "statik": "Statikstempel",
    "sasv": "Wärme-/Schallschutzstempel",
}

PROFILE_LABELS = {
    "statik": "Statikberechnung - feste Position",
    "plan": "Statikplan - feste Position im Plankopf",
    "sasv": "Wärme-/Schallschutz - feste Position",
    "free": "Freie Position",
}


def _load_fitz():
    vendor = BASE / "_vendor"
    if vendor.exists() and str(vendor) not in sys.path:
        sys.path.insert(0, str(vendor))
    errors = []
    for name in ("pymupdf", "fitz"):
        try:
            return importlib.import_module(name)
        except Exception as exc:  # pragma: no cover - only used on broken installs
            errors.append(f"{name}: {exc}")
    raise RuntimeError(
        "Die lokale PDF-Engine konnte nicht geladen werden. "
        "Bitte das Update erneut ausführen. " + " | ".join(errors)
    )


def _asset_path(stamp_kind: str) -> Path:
    filename = STAMP_FILES[stamp_kind]
    local_root = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    local = local_root / "Engbers Projektzentrale" / "assets" / LOCAL_STAMP_FILES[stamp_kind]
    candidates = (local, BASE / "assets" / filename, BASE / filename)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Stempeldatei fehlt: {filename}")


def _configured_asset_path(stamp_kind: str) -> Path:
    local_root = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    return local_root / "Engbers Projektzentrale" / "assets" / LOCAL_STAMP_FILES[stamp_kind]


def _extract_stamp_from_pdf(pdf_path: Path, stamp_kind: str) -> bytes:
    """Extract the most likely existing stamp image from first/last PDF page."""
    fitz = _load_fitz()
    document = fitz.open(str(pdf_path))
    try:
        if len(document) < 1:
            raise RuntimeError("Die PDF enthält keine Seite.")
        target_aspect = 2.1 if stamp_kind == "statik" else 1.5
        pages = tuple(dict.fromkeys((0, len(document) - 1)))
        candidates = []
        for page_index in pages:
            page = document[page_index]
            for info in page.get_images(full=True):
                xref = int(info[0])
                width = max(1, int(info[2]))
                height = max(1, int(info[3]))
                aspect = width / float(height)
                if not 1.15 <= aspect <= 3.2 or width < 80 or height < 35:
                    continue
                score = abs(aspect - target_aspect) - min(width * height, 500000) / 5000000.0
                candidates.append((score, xref))
        if not candidates:
            raise RuntimeError("In der PDF wurde keine geeignete Stempelgrafik gefunden.")
        _score, xref = min(candidates, key=lambda item: item[0])
        pix = fitz.Pixmap(document, xref)
        if pix.colorspace is None:
            raise RuntimeError("Die gefundene Grafik besitzt keinen lesbaren Farbraum.")
        if int(pix.colorspace.n) != 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        return pix.tobytes("png")
    finally:
        document.close()


def configure_stamp_asset(parent, stamp_kind: str):
    source = filedialog.askopenfilename(
        parent=parent,
        title=STAMP_LABELS[stamp_kind] + " auswählen",
        filetypes=[("PNG oder bereits gestempelte PDF", "*.png *.pdf"), ("Alle Dateien", "*.*")],
    )
    if not source:
        return None
    source = Path(source)
    target = _configured_asset_path(stamp_kind)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.stem + ".tmp.png")
    try:
        if source.suffix.lower() == ".pdf":
            temporary.write_bytes(_extract_stamp_from_pdf(source, stamp_kind))
        elif source.suffix.lower() == ".png":
            shutil.copy2(source, temporary)
        else:
            raise RuntimeError("Bitte eine PNG-Datei oder eine bereits gestempelte PDF auswählen.")
        # Validate before replacing the locally configured stamp.
        fitz = _load_fitz()
        check = fitz.Pixmap(str(temporary))
        if check.width < 20 or check.height < 20:
            raise RuntimeError("Die ausgewählte Stempelgrafik ist zu klein.")
        os.replace(temporary, target)
        return target
    finally:
        try:
            temporary.unlink()
        except Exception:
            pass


def _clean_stamp_bytes(stamp_kind: str) -> tuple[bytes, float]:
    """Return transparent PNG bytes and its width/height aspect ratio."""
    fitz = _load_fitz()
    source = fitz.Pixmap(str(_asset_path(stamp_kind)))
    if source.colorspace is None:
        raise RuntimeError("Die Stempelgrafik besitzt keinen lesbaren Farbraum.")
    if int(source.colorspace.n) != 3:
        source = fitz.Pixmap(fitz.csRGB, source)
    stamp = fitz.Pixmap(source, 1)
    samples = bytes(stamp.samples)
    channels = int(stamp.n)
    if channels != 4:
        raise RuntimeError("Die Stempelgrafik konnte nicht in RGBA umgewandelt werden.")
    alpha = bytearray(stamp.width * stamp.height)
    ai = 0
    for pos in range(0, len(samples), channels):
        red, green, blue, original_alpha = samples[pos : pos + 4]
        minimum = min(red, green, blue)
        value = original_alpha
        if minimum >= 245:
            value = 0
        elif minimum > 220:
            value = round(value * (245 - minimum) / 25.0)
        alpha[ai] = max(0, min(255, value))
        ai += 1
    stamp.set_alpha(bytes(alpha), premultiply=0)
    data = stamp.tobytes("png")
    aspect = float(stamp.width) / max(1.0, float(stamp.height))
    return data, aspect


def _profile_stamp_kind(profile: str, free_stamp_kind: str = "statik") -> str:
    if profile in ("statik", "plan"):
        return "statik"
    if profile == "sasv":
        return "sasv"
    return free_stamp_kind


def fixed_rect(profile: str, page_width: float, page_height: float, aspect: float):
    """Return a PyMuPDF rectangle for the measured fixed profiles."""
    fitz = _load_fitz()
    if profile == "statik":
        # Measured from the supplied A4 mb-Viewer reference calculation.
        ref_w, ref_h = 595.2755737304688, 841.8897705078125
        left = 409.9108581542969 * page_width / ref_w
        top = 453.3632507324219 * page_height / ref_h
        width = 152.6400451660156 * page_width / ref_w
    elif profile == "statik_last":
        # Separate measured signature position on the mb closing page.
        ref_w, ref_h = 595.2755737304688, 841.8897705078125
        left = 187.9443359375 * page_width / ref_w
        top = 326.85791015625 * page_height / ref_h
        width = 152.6400146484375 * page_width / ref_w
    elif profile == "plan":
        # Same physical stamp size as the calculation. The placement is
        # anchored to the lower-right Allplan title block and therefore also
        # works for other plan formats with the same title-block convention.
        width = 152.6400451660156
        right_margin = 285.072509765625
        bottom_margin = 65.1953125
        height = width / aspect
        left = page_width - right_margin - width
        top = page_height - bottom_margin - height
        if left < 0 or top < 0:
            scale = min(page_width / 3370.389892578125, page_height / 2383.93994140625)
            width = max(45.0, width * scale)
            height = width / aspect
            left = max(8.0, page_width - right_margin * scale - width)
            top = max(8.0, page_height - bottom_margin * scale - height)
    elif profile == "sasv":
        # Existing, proven position from the Word-certificate workflow.
        ref_w, ref_h = 595.28, 841.89
        left = 220.0 * page_width / ref_w
        top = 575.0 * page_height / ref_h
        width = 210.0 * page_width / ref_w
    else:
        raise ValueError(f"Unbekanntes Profil: {profile}")
    height = width / aspect
    left = max(0.0, min(left, max(0.0, page_width - width)))
    top = max(0.0, min(top, max(0.0, page_height - height)))
    return fitz.Rect(left, top, left + width, top + height)


def _default_free_rect(page_width: float, page_height: float, aspect: float, stamp_kind: str):
    fitz = _load_fitz()
    width = 152.64 if stamp_kind == "statik" else 210.0
    width = min(width, page_width * 0.48)
    height = width / aspect
    left = max(10.0, page_width - width - 24.0)
    top = max(10.0, page_height - height - 24.0)
    return fitz.Rect(left, top, left + width, top + height)


def _pdf_has_signatures(document) -> bool:
    try:
        # PyMuPDF returns -1 when no AcroForm/signature information exists.
        if int(document.get_sigflags() or 0) > 0:
            return True
    except Exception:
        pass
    try:
        for page in document:
            widget = page.first_widget
            while widget:
                if int(getattr(widget, "field_type", 0)) == 6:
                    return True
                widget = widget.next
    except Exception:
        pass
    return False


def stamp_pdf(
    source_pdf,
    output_pdf,
    profile,
    stamp_kind=None,
    page_index=0,
    all_pages=False,
    free_rect=None,
):
    """Stamp a PDF and atomically create the requested output file."""
    fitz = _load_fitz()
    source_pdf = Path(source_pdf).resolve()
    output_pdf = Path(output_pdf).resolve()
    if not source_pdf.exists():
        raise FileNotFoundError("Die ausgewählte PDF wurde nicht gefunden.")
    if source_pdf.suffix.lower() != ".pdf":
        raise ValueError("Bitte eine PDF-Datei auswählen.")
    stamp_kind = _profile_stamp_kind(profile, stamp_kind or "statik")
    stamp_bytes, aspect = _clean_stamp_bytes(stamp_kind)
    document = fitz.open(str(source_pdf))
    temporary = output_pdf.with_name(
        output_pdf.stem
        + f".pzstamp_{_dt.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        + output_pdf.suffix
    )
    try:
        if len(document) < 1:
            raise RuntimeError("Die PDF enthält keine Seite.")
        if getattr(document, "needs_pass", False):
            raise RuntimeError("Kennwortgeschützte PDFs können nicht gestempelt werden.")
        if _pdf_has_signatures(document):
            raise RuntimeError(
                "Die PDF enthält bereits eine digitale Signatur. "
                "Sie darf nach der Signatur nicht mehr verändert werden."
            )
        page_index = max(0, min(int(page_index), len(document) - 1))
        if profile == "statik":
            # A calculation is signed on both cover and closing page.
            targets = tuple(dict.fromkeys((0, len(document) - 1)))
        elif profile == "plan":
            # Every plan page carries its own title block.
            targets = range(len(document))
        elif profile == "sasv":
            targets = (0,)
        else:
            targets = range(len(document)) if all_pages else (page_index,)
        source_page = document[page_index]
        source_width = float(source_page.rect.width)
        source_height = float(source_page.rect.height)
        normalized = None
        if profile == "free":
            rect = free_rect or _default_free_rect(
                source_width, source_height, aspect, stamp_kind
            )
            normalized = (
                float(rect.x0) / source_width,
                float(rect.y0) / source_height,
                float(rect.x1) / source_width,
                float(rect.y1) / source_height,
            )
        for index in targets:
            page = document[index]
            page_width = float(page.rect.width)
            page_height = float(page.rect.height)
            if profile == "free":
                x0, y0, x1, y1 = normalized
                rect = fitz.Rect(
                    x0 * page_width,
                    y0 * page_height,
                    x1 * page_width,
                    y1 * page_height,
                )
            else:
                page_profile = profile
                if profile == "statik" and len(document) > 1 and index == len(document) - 1:
                    page_profile = "statik_last"
                rect = fixed_rect(page_profile, page_width, page_height, aspect)
            page.insert_image(
                rect,
                stream=stamp_bytes,
                keep_proportion=True,
                overlay=True,
            )
        temporary.parent.mkdir(parents=True, exist_ok=True)
        document.save(str(temporary), garbage=3, deflate=True)
    finally:
        document.close()
    if not temporary.exists() or temporary.stat().st_size < 100:
        raise RuntimeError("Es wurde keine gültige gestempelte PDF erzeugt.")
    check = fitz.open(str(temporary))
    try:
        original = fitz.open(str(source_pdf))
        try:
            if len(check) != len(original):
                raise RuntimeError("Die Seitenzahl hat sich beim Stempeln verändert.")
        finally:
            original.close()
    finally:
        check.close()
    try:
        os.replace(temporary, output_pdf)
    except PermissionError as exc:
        raise RuntimeError(
            "Die PDF ist noch in einem PDF-Programm geöffnet. "
            "Bitte schließen und erneut versuchen."
        ) from exc
    return output_pdf


def _open_path(path: Path):
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


class PdfStampDialog(tk.Toplevel):
    def __init__(self, parent=None, initial_pdf=None, initial_profile="statik"):
        super().__init__(parent)
        self.title("PDF stempeln")
        self.geometry("1180x800")
        self.minsize(940, 680)
        self.transient(parent if parent and parent.winfo_exists() else None)
        self.pdf_path = Path(initial_pdf).resolve() if initial_pdf else None
        self.document = None
        self.page_index = 0
        self.page_photo = None
        self.stamp_photo = None
        self.canvas_page_box = None
        self.free_rect = None
        self.drag_mode = None
        self.drag_start = None
        self.drag_rect_start = None

        self.profile_var = tk.StringVar(value=initial_profile)
        self.stamp_var = tk.StringVar(value="statik")
        self.scope_var = tk.StringVar(value="current")
        self.replace_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="PDF auswählen")

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._close)
        if self.pdf_path:
            self.after(50, self._load_pdf)

    def _build_ui(self):
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        ttk.Button(top, text="PDF auswählen", command=self._choose_pdf).pack(side="left")
        self.file_label = ttk.Label(top, text="Keine PDF ausgewählt")
        self.file_label.pack(side="left", padx=12, fill="x", expand=True)

        body = ttk.Frame(self, padding=(12, 0, 12, 12))
        body.pack(fill="both", expand=True)
        controls = ttk.LabelFrame(body, text="Stempel und Position", padding=12)
        controls.pack(side="left", fill="y", padx=(0, 12))

        ttk.Label(controls, text="Arbeitsweise").pack(anchor="w")
        for key in ("statik", "plan", "sasv", "free"):
            ttk.Radiobutton(
                controls,
                text=PROFILE_LABELS[key],
                value=key,
                variable=self.profile_var,
                command=self._profile_changed,
            ).pack(anchor="w", pady=2)

        ttk.Separator(controls).pack(fill="x", pady=12)
        ttk.Label(controls, text="Stempel im freien Modus").pack(anchor="w")
        self.stamp_combo = ttk.Combobox(
            controls,
            state="readonly",
            textvariable=self.stamp_var,
            values=("statik", "sasv"),
            width=25,
        )
        self.stamp_combo.pack(fill="x", pady=(4, 2))
        self.stamp_combo.bind("<<ComboboxSelected>>", self._stamp_changed)
        self.stamp_hint = ttk.Label(controls, text=STAMP_LABELS["statik"])
        self.stamp_hint.pack(anchor="w")

        ttk.Separator(controls).pack(fill="x", pady=12)
        ttk.Label(controls, text="Stempel lokal einrichten").pack(anchor="w")
        ttk.Button(
            controls,
            text="Statikstempel einrichten",
            command=lambda: self._configure_stamp("statik"),
        ).pack(fill="x", pady=(4, 2))
        ttk.Button(
            controls,
            text="Wärme-/Schallschutz einrichten",
            command=lambda: self._configure_stamp("sasv"),
        ).pack(fill="x", pady=2)
        ttk.Label(
            controls,
            text="PNG oder bereits gestempelte PDF.\nDie Grafik bleibt nur auf diesem Rechner.",
            justify="left",
        ).pack(anchor="w", pady=(2, 0))

        ttk.Separator(controls).pack(fill="x", pady=12)
        ttk.Label(controls, text="Seiten").pack(anchor="w")
        ttk.Radiobutton(
            controls,
            text="Nur angezeigte Seite",
            value="current",
            variable=self.scope_var,
        ).pack(anchor="w", pady=2)
        ttk.Radiobutton(
            controls,
            text="Alle Seiten",
            value="all",
            variable=self.scope_var,
        ).pack(anchor="w", pady=2)

        ttk.Separator(controls).pack(fill="x", pady=12)
        ttk.Checkbutton(
            controls,
            text="Original-PDF ersetzen",
            variable=self.replace_var,
        ).pack(anchor="w")
        ttk.Label(
            controls,
            text="Ohne Haken entsteht eine neue Datei\nmit dem Zusatz _gestempelt.",
            justify="left",
        ).pack(anchor="w", pady=(2, 12))
        ttk.Button(
            controls,
            text="PDF JETZT STEMPELN",
            command=self._apply,
        ).pack(fill="x", pady=(10, 4))
        ttk.Button(controls, text="Schließen", command=self._close).pack(fill="x")

        preview = ttk.LabelFrame(body, text="PDF-Vorschau", padding=8)
        preview.pack(side="left", fill="both", expand=True)
        nav = ttk.Frame(preview)
        nav.pack(fill="x", pady=(0, 6))
        ttk.Button(nav, text="<", width=4, command=self._previous_page).pack(side="left")
        self.page_label = ttk.Label(nav, text="Seite - / -")
        self.page_label.pack(side="left", padx=10)
        ttk.Button(nav, text=">", width=4, command=self._next_page).pack(side="left")
        ttk.Label(
            nav,
            text="Im freien Modus: Stempel ziehen, Ecke rechts unten zum Skalieren.",
        ).pack(side="right")

        self.canvas = tk.Canvas(preview, bg="#777777", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._render())
        self.canvas.bind("<ButtonPress-1>", self._mouse_down)
        self.canvas.bind("<B1-Motion>", self._mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._mouse_up)

        status = ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(12, 6))
        status.pack(fill="x")
        self._profile_changed()

    def _choose_pdf(self):
        filename = filedialog.askopenfilename(
            parent=self,
            title="PDF auswählen",
            filetypes=[("PDF-Dateien", "*.pdf"), ("Alle Dateien", "*.*")],
        )
        if not filename:
            return
        self.pdf_path = Path(filename).resolve()
        self.page_index = 0
        self._load_pdf()

    def _configure_stamp(self, stamp_kind):
        try:
            path = configure_stamp_asset(self, stamp_kind)
            if path:
                self.status_var.set(STAMP_LABELS[stamp_kind] + " wurde lokal eingerichtet")
                messagebox.showinfo(
                    "Stempel eingerichtet",
                    STAMP_LABELS[stamp_kind] + " wurde lokal gespeichert.\n\nDie Datei wird nicht online übertragen.",
                    parent=self,
                )
                self._render()
        except Exception as exc:
            messagebox.showerror("Stempel einrichten", str(exc), parent=self)

    def _load_pdf(self):
        try:
            if self.document is not None:
                self.document.close()
            self.document = _load_fitz().open(str(self.pdf_path))
            if len(self.document) < 1:
                raise RuntimeError("Die PDF enthält keine Seite.")
            if getattr(self.document, "needs_pass", False):
                raise RuntimeError("Kennwortgeschützte PDFs können nicht gestempelt werden.")
            self.file_label.configure(text=str(self.pdf_path))
            self.status_var.set(f"{len(self.document)} Seite(n) geladen")
            self._reset_free_rect()
            self._render()
        except Exception as exc:
            self.document = None
            messagebox.showerror("PDF stempeln", str(exc), parent=self)

    def _current_stamp_kind(self):
        return _profile_stamp_kind(self.profile_var.get(), self.stamp_var.get())

    def _reset_free_rect(self):
        if self.document is None:
            return
        page = self.document[self.page_index]
        _, aspect = _clean_stamp_bytes(self._current_stamp_kind())
        self.free_rect = _default_free_rect(
            float(page.rect.width),
            float(page.rect.height),
            aspect,
            self._current_stamp_kind(),
        )

    def _profile_changed(self):
        is_free = self.profile_var.get() == "free"
        self.stamp_combo.configure(state="readonly" if is_free else "disabled")
        self.stamp_hint.configure(text=STAMP_LABELS[self._current_stamp_kind()])
        if self.profile_var.get() == "statik":
            self.status_var.set("Feste Position: erste und letzte Seite")
        elif self.profile_var.get() == "plan":
            self.status_var.set("Feste Position: auf jedem Plan unten rechts im Schriftfeld")
        elif self.profile_var.get() == "sasv":
            self.status_var.set("Feste Position: erste Seite")
        if self.document is not None:
            if is_free and self.free_rect is None:
                self._reset_free_rect()
            self._render()

    def _stamp_changed(self, _event=None):
        self.stamp_hint.configure(text=STAMP_LABELS[self._current_stamp_kind()])
        self._reset_free_rect()
        self._render()

    def _previous_page(self):
        if self.document is None or self.page_index <= 0:
            return
        self.page_index -= 1
        self._reset_free_rect()
        self._render()

    def _next_page(self):
        if self.document is None or self.page_index >= len(self.document) - 1:
            return
        self.page_index += 1
        self._reset_free_rect()
        self._render()

    def _page_display_box(self, page):
        canvas_width = max(10, self.canvas.winfo_width())
        canvas_height = max(10, self.canvas.winfo_height())
        scale = min(
            (canvas_width - 20) / float(page.rect.width),
            (canvas_height - 20) / float(page.rect.height),
        )
        scale = max(0.05, scale)
        width = float(page.rect.width) * scale
        height = float(page.rect.height) * scale
        x = (canvas_width - width) / 2.0
        y = (canvas_height - height) / 2.0
        return x, y, width, height, scale

    def _rect_for_preview(self, page):
        stamp_kind = self._current_stamp_kind()
        _, aspect = _clean_stamp_bytes(stamp_kind)
        if self.profile_var.get() == "free":
            if self.free_rect is None:
                self._reset_free_rect()
            return self.free_rect
        profile = self.profile_var.get()
        if profile == "statik" and len(self.document) > 1 and self.page_index == len(self.document) - 1:
            profile = "statik_last"
        return fixed_rect(
            profile,
            float(page.rect.width),
            float(page.rect.height),
            aspect,
        )

    def _render(self):
        if self.document is None or self.canvas.winfo_width() < 40:
            return
        try:
            page = self.document[self.page_index]
            x, y, width, height, scale = self._page_display_box(page)
            pix = page.get_pixmap(matrix=_load_fitz().Matrix(scale, scale), alpha=False)
            page_data = base64.b64encode(pix.tobytes("png")).decode("ascii")
            self.page_photo = tk.PhotoImage(data=page_data)
            self.canvas.delete("all")
            self.canvas.create_image(x, y, image=self.page_photo, anchor="nw", tags="page")
            self.canvas_page_box = (x, y, width, height, scale)

            rect = self._rect_for_preview(page)
            sx0 = x + float(rect.x0) * scale
            sy0 = y + float(rect.y0) * scale
            sx1 = x + float(rect.x1) * scale
            sy1 = y + float(rect.y1) * scale
            stamp_bytes, _ = _clean_stamp_bytes(self._current_stamp_kind())
            image_doc = _load_fitz().open(stream=stamp_bytes, filetype="png")
            try:
                image_page = image_doc[0]
                target_w = max(1, int(sx1 - sx0))
                target_h = max(1, int(sy1 - sy0))
                matrix = _load_fitz().Matrix(
                    target_w / float(image_page.rect.width),
                    target_h / float(image_page.rect.height),
                )
                stamp_pix = image_page.get_pixmap(matrix=matrix, alpha=True)
            finally:
                image_doc.close()
            stamp_data = base64.b64encode(stamp_pix.tobytes("png")).decode("ascii")
            self.stamp_photo = tk.PhotoImage(data=stamp_data)
            self.canvas.create_image(
                sx0, sy0, image=self.stamp_photo, anchor="nw", tags="stamp"
            )
            outline = "#b08b49" if self.profile_var.get() == "free" else "#2f6f9f"
            self.canvas.create_rectangle(
                sx0, sy0, sx1, sy1, outline=outline, width=2, tags="stampbox"
            )
            if self.profile_var.get() == "free":
                self.canvas.create_rectangle(
                    sx1 - 7,
                    sy1 - 7,
                    sx1 + 7,
                    sy1 + 7,
                    fill="#b08b49",
                    outline="white",
                    tags="handle",
                )
            self.page_label.configure(
                text=f"Seite {self.page_index + 1} / {len(self.document)}"
            )
        except Exception as exc:
            self.status_var.set("Vorschaufehler: " + str(exc))

    def _screen_stamp_rect(self):
        if self.document is None or self.canvas_page_box is None:
            return None
        page = self.document[self.page_index]
        rect = self._rect_for_preview(page)
        x, y, _width, _height, scale = self.canvas_page_box
        return (
            x + float(rect.x0) * scale,
            y + float(rect.y0) * scale,
            x + float(rect.x1) * scale,
            y + float(rect.y1) * scale,
        )

    def _mouse_down(self, event):
        if self.profile_var.get() != "free" or self.free_rect is None:
            return
        screen_rect = self._screen_stamp_rect()
        if not screen_rect:
            return
        x0, y0, x1, y1 = screen_rect
        if not (x0 - 8 <= event.x <= x1 + 8 and y0 - 8 <= event.y <= y1 + 8):
            return
        self.drag_mode = "resize" if abs(event.x - x1) <= 16 and abs(event.y - y1) <= 16 else "move"
        self.drag_start = (event.x, event.y)
        self.drag_rect_start = tuple(self.free_rect)

    def _mouse_move(self, event):
        if not self.drag_mode or self.document is None or self.canvas_page_box is None:
            return
        page = self.document[self.page_index]
        _x, _y, _w, _h, scale = self.canvas_page_box
        dx = (event.x - self.drag_start[0]) / scale
        dy = (event.y - self.drag_start[1]) / scale
        x0, y0, x1, y1 = self.drag_rect_start
        _, aspect = _clean_stamp_bytes(self._current_stamp_kind())
        if self.drag_mode == "move":
            width, height = x1 - x0, y1 - y0
            nx0 = max(0.0, min(x0 + dx, float(page.rect.width) - width))
            ny0 = max(0.0, min(y0 + dy, float(page.rect.height) - height))
            self.free_rect = _load_fitz().Rect(nx0, ny0, nx0 + width, ny0 + height)
        else:
            width = max(40.0, x1 - x0 + dx)
            width = min(width, float(page.rect.width) - x0)
            height = width / aspect
            if y0 + height > float(page.rect.height):
                height = float(page.rect.height) - y0
                width = height * aspect
            self.free_rect = _load_fitz().Rect(x0, y0, x0 + width, y0 + height)
        self._render()

    def _mouse_up(self, _event):
        self.drag_mode = None
        self.drag_start = None
        self.drag_rect_start = None

    def _output_path(self):
        if self.replace_var.get():
            return self.pdf_path
        candidate = self.pdf_path.with_name(self.pdf_path.stem + "_gestempelt.pdf")
        if not candidate.exists():
            return candidate
        index = 2
        while True:
            candidate = self.pdf_path.with_name(
                self.pdf_path.stem + f"_gestempelt_{index}.pdf"
            )
            if not candidate.exists():
                return candidate
            index += 1

    def _apply(self):
        if self.document is None or not self.pdf_path:
            messagebox.showwarning("PDF stempeln", "Bitte zuerst eine PDF auswählen.", parent=self)
            return
        output = self._output_path()
        if self.replace_var.get():
            ok = messagebox.askyesno(
                "Original ersetzen",
                "Die ausgewählte Original-PDF wird durch die gestempelte Fassung ersetzt.\n\nFortfahren?",
                parent=self,
            )
            if not ok:
                return
        try:
            if self.document is not None:
                self.document.close()
                self.document = None
            result = stamp_pdf(
                self.pdf_path,
                output,
                self.profile_var.get(),
                stamp_kind=self.stamp_var.get(),
                page_index=self.page_index,
                all_pages=self.scope_var.get() == "all",
                free_rect=self.free_rect,
            )
            messagebox.showinfo(
                "PDF gestempelt",
                f"Die gestempelte PDF wurde erstellt:\n\n{result}",
                parent=self,
            )
            _open_path(result)
            self.pdf_path = result
            self._load_pdf()
        except Exception as exc:
            messagebox.showerror("PDF stempeln", str(exc), parent=self)
            self._load_pdf()

    def _close(self):
        try:
            if self.document is not None:
                self.document.close()
        finally:
            self.destroy()


def open_pdf_stamp_dialog(parent=None, initial_pdf=None, initial_profile="statik"):
    return PdfStampDialog(parent, initial_pdf=initial_pdf, initial_profile=initial_profile)


if __name__ == "__main__":  # manual standalone test/use
    root = tk.Tk()
    root.withdraw()
    dialog = PdfStampDialog(root)
    dialog.grab_set()
    root.mainloop()
