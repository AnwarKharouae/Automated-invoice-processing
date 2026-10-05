import os
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl
from core.paths import resource_path

class SoundPlayer:
    def __init__(self):
        self.player = QMediaPlayer()
        self.audio = QAudioOutput()
        self.audio.setVolume(0.7)
        self.player.setAudioOutput(self.audio)
        self._base = resource_path("sounds")

    def play(self, name):
        path = os.path.join(self._base, name)
        if not os.path.exists(path):
            print(f"[sound] missing: {path}")
            return

        url = QUrl.fromLocalFile(os.path.abspath(path))
        if self.player.source() == url:
            # Same track — rewind and replay
            self.player.setPosition(0)
            self.player.play()
        else:
            # Different track — load and play
            self.player.setSource(url)
            self.player.play()


# module-level singleton so audio doesn't get garbage collected
_player = None

def get_player():
    global _player
    if _player is None:
        _player = SoundPlayer()
    return _player