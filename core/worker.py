from PySide6.QtCore import QThread, Signal
import os
import traceback

from core.pipeline import (
    preprocess_all, deepseek_ocr_all, structure_all,
    paddle_spot_all, locate_and_draw_all,
)


class BatchWorker(QThread):
    """
    Runs the whole batch in the correct order:
        1. Preprocess all
        2. DeepSeek OCR on ALL invoices     ← model stays loaded for whole batch
        3. Kill DeepSeek (done by caller)
        4. Load Llama + Paddle
        5. Llama structures ALL
        6. Paddle spots ALL
        7. Locate + draw each
    """
    deepseek_reloaded = Signal()
    phase      = Signal(str)              # "ocr" | "structure" | "spotting" | "drawing"
    progress   = Signal(int, int, str)    # (current, total, filename)
    one_done   = Signal(str, dict)        # (filename, result)
    one_failed = Signal(str, str)
    finished_  = Signal()

    def __init__(self, invoice_paths, schema_prompt, output_folder, ollama_mgr):
        super().__init__()
        self.invoice_paths = invoice_paths
        self.schema_prompt = schema_prompt
        self.output_folder = output_folder
        self.mgr = ollama_mgr
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            total = len(self.invoice_paths)

            # --- PHASE 1: preprocess ---
            self.phase.emit("preprocess")
            self.progress.emit(0, total, "Preprocessing all invoices...")
            preprocessed = preprocess_all(self.invoice_paths)

            if self._cancel:
                self.finished_.emit(); return

            # --- PHASE 2: DeepSeek OCR on ALL ---
                        # --- PHASE 2: DeepSeek OCR on ALL ---
            self.phase.emit("ocr")
            # Free VRAM from any previous batch before loading the big model
            self.mgr.kill_batch_models()
            self.mgr.load_deepseek()
            ocr_results = {}
            for i, (filename, img_bytes) in enumerate(preprocessed.items(), 1):
                if self._cancel:
                    break
                self.progress.emit(i, total, f"OCR: {filename}")
                try:
                    from core.pipeline import run_deepseek_ocr
                    ocr_results[filename] = run_deepseek_ocr(img_bytes)
                except Exception as e:
                    self.one_failed.emit(filename, f"OCR failed: {e}")
            self.mgr.kill_deepseek()

            if self._cancel:
                self.finished_.emit(); return

            # --- PHASE 3: load Llama + Paddle ---
            self.mgr.load_batch_models()

            # --- PHASE 4: Llama structures ALL ---
            self.phase.emit("structure")
            structured = {}
            for i, (filename, raw_text) in enumerate(ocr_results.items(), 1):
                if self._cancel:
                    break
                self.progress.emit(i, total, f"Structuring: {filename}")
                try:
                    from core.pipeline import structure_with_llama, normalize_extraction
                    parsed = structure_with_llama(raw_text, self.schema_prompt)
                    structured[filename] = normalize_extraction(parsed)
                except Exception as e:
                    self.one_failed.emit(filename, f"Structure failed: {e}")

            if self._cancel:
                self.finished_.emit(); return

            # --- PHASE 5: Paddle spots ALL ---
            self.phase.emit("spotting")
            spotting = {}
            for i, (filename, img_bytes) in enumerate(preprocessed.items(), 1):
                if self._cancel:
                    break
                self.progress.emit(i, total, f"Spotting: {filename}")
                try:
                    from core.pipeline import run_paddle_spotting, parse_paddle_spotting
                    from PIL import Image
                    raw = run_paddle_spotting(img_bytes)
                    path = next(p for p in self.invoice_paths if os.path.basename(p) == filename)
                    with Image.open(path) as im:
                        W, H = im.size
                    spotting[filename] = parse_paddle_spotting(raw, W, H)
                except Exception as e:
                    self.one_failed.emit(filename, f"Spotting failed: {e}")

            if self._cancel:
                self.finished_.emit(); return

            # --- PHASE 6: locate + draw each ---
            self.phase.emit("drawing")
            from core.pipeline import locate_values, draw_boxes
            os.makedirs(self.output_folder, exist_ok=True)
            by_name = {os.path.basename(p): p for p in self.invoice_paths}

            for i, (filename, data) in enumerate(structured.items(), 1):
                if self._cancel:
                    break
                self.progress.emit(i, total, f"Locating: {filename}")
                try:
                    lines = spotting.get(filename, [])
                    located = locate_values(data["details"], data["items"], lines)
                    annotated = os.path.join(self.output_folder, f"annotated_{filename}")
                    draw_boxes(by_name[filename], located, annotated)
                    self.one_done.emit(filename, {
                        "file": filename,
                        "path": by_name[filename],
                        "annotated_path": annotated,
                        "details": data["details"],
                        "items": data["items"],
                        "located": located,
                    })
                except Exception as e:
                    self.one_failed.emit(filename, f"Draw failed: {e}")

        except Exception as e:
            tb = traceback.format_exc()
            self.one_failed.emit("BATCH", f"{e}\n{tb}")
        finally:
            self.finished_.emit()
            # Prepare for the next batch: free Llama+Paddle, reload DeepSeek warm
            try:
                self.mgr.kill_batch_models()
                self.mgr.load_deepseek()
                self.deepseek_reloaded.emit()      # ← add this
            except Exception as e:
                print(f"[worker] post-batch cleanup failed: {e}")