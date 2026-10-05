"""
Path helpers. Every file the app touches (resources, sessions,
annotated images) is resolved relative to the app folder — not the
current working directory.
"""

import os
import sys


def app_dir():
    """Folder where the app lives.
    - Frozen EXE: the folder containing the exe
    - Python script: the project root (one level above core/)
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts):
    """Path inside <app_dir>/resources/"""
    return os.path.join(app_dir(), "resources", *parts)


def work_path(*parts):
    """Any path relative to <app_dir>/ — for sessions, annotated_batch, etc."""
    return os.path.join(app_dir(), *parts)