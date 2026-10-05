import ollama


class OllamaManager:
    """
    Handles loading and killing the three models at the right moments.

    Lifecycle per session:
        app opens      → load_deepseek()
        process batch  → kill_deepseek() → load_batch_models() → run → kill_batch_models()
        user approves  → optionally load_deepseek() again
        app closes     → kill_all()
    """

    DEEPSEEK = "deepseek-ocr"
    LLAMA    = "llama3.2:3b"
    PADDLE   = "seriouswebby/paddleocr-vl-1.6:spotting"

    def __init__(self, log=print):
        self.log = log
        self.loaded = set()

    # ---------------------------------------------------------------
    # low-level helpers
    # ---------------------------------------------------------------
    def _warm(self, model):
        """Pin a model into VRAM indefinitely (-1)."""
        try:
            ollama.chat(model=model, keep_alive=-1)
            self.loaded.add(model)
            self.log(f"   loaded: {model}")
            return True
        except Exception as e:
            self.log(f"   FAILED to load {model}: {e}")
            return False

    def _kill(self, model):
        """Unload a model from VRAM immediately."""
        try:
            ollama.chat(model=model, keep_alive=0)
            self.loaded.discard(model)
            self.log(f"   killed: {model}")
            return True
        except Exception as e:
            self.log(f"   FAILED to kill {model}: {e}")
            return False

    def _is_available(self, model):
        """Check that the model exists in the local Ollama store."""
        try:
            listing = ollama.list()
            names = [m.get("model", m.get("name", "")) for m in listing.get("models", [])]
            return any(model in n for n in names)
        except Exception as e:
            self.log(f"   cannot list models: {e}")
            return False

    # ---------------------------------------------------------------
    # public API
    # ---------------------------------------------------------------
    def check_ollama(self):
        """Returns True if the Ollama server is reachable."""
        try:
            ollama.list()
            return True
        except Exception:
            return False

    def check_models_available(self):
        """Returns {model_name: bool} for the three models we need."""
        return {
            self.DEEPSEEK: self._is_available(self.DEEPSEEK),
            self.LLAMA:    self._is_available(self.LLAMA),
            self.PADDLE:   self._is_available(self.PADDLE),
        }

    def load_deepseek(self):
        return self._warm(self.DEEPSEEK)

    def kill_deepseek(self):
        return self._kill(self.DEEPSEEK)

    def load_batch_models(self):
        """Load Llama and Paddle together for the batch processing phase."""
        ok_l = self._warm(self.LLAMA)
        ok_p = self._warm(self.PADDLE)
        return ok_l and ok_p

    def kill_batch_models(self):
        self._kill(self.LLAMA)
        self._kill(self.PADDLE)

    def kill_all(self):
        for m in list(self.loaded):
            self._kill(m)