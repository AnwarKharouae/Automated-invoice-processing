import os
import json
import zipfile
import shutil
from datetime import datetime
from core.paths import work_path


SESSION_VERSION = 1
SESSIONS_DIR = work_path("sessions")


def save_session(review_data, invoice_files, schema_text, output_zip):
    """Bundle the current review into a portable zip. Returns output_zip."""
    tmp_dir = output_zip + ".tmp"
    if os.path.exists(tmp_dir):
        shutil.rmtree(tmp_dir, ignore_errors=True)
    os.makedirs(tmp_dir, exist_ok=True)

    try:
        session = {
            "version": SESSION_VERSION,
            "saved_at": datetime.now().isoformat(),
            "invoice_files": invoice_files,
            "review_data": review_data,
        }
        with open(os.path.join(tmp_dir, "session.json"), "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2, ensure_ascii=False)

        with open(os.path.join(tmp_dir, "schema.txt"), "w", encoding="utf-8") as f:
            f.write(schema_text or "")

        ann_dir = os.path.join(tmp_dir, "annotated")
        os.makedirs(ann_dir, exist_ok=True)
        for fname, data in review_data.items():
            src = data.get("annotated_path")
            if src and os.path.exists(src):
                shutil.copy2(src, os.path.join(ann_dir, os.path.basename(src)))

        if os.path.exists(output_zip):
            os.remove(output_zip)
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(tmp_dir):
                for file in files:
                    full = os.path.join(root, file)
                    rel = os.path.relpath(full, tmp_dir)
                    zf.write(full, rel)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return output_zip


def load_session(zip_path):
    """Extract to sessions/<name>/ and return the data.
    Returns dict with: name, folder, invoice_files, review_data, schema."""
    if not os.path.exists(zip_path):
        raise FileNotFoundError(zip_path)

    name = os.path.splitext(os.path.basename(zip_path))[0]
    extract_dir = os.path.join(SESSIONS_DIR, name)
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir)
    os.makedirs(extract_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    session_json = os.path.join(extract_dir, "session.json")
    if not os.path.exists(session_json):
        raise ValueError("Invalid session file: session.json missing")

    with open(session_json, "r", encoding="utf-8") as f:
        session = json.load(f)

    if session.get("version") != SESSION_VERSION:
        raise ValueError(
            f"Session version {session.get('version')} not supported "
            f"(expected {SESSION_VERSION})"
        )

    # repoint annotated paths to extracted copies
    ann_dir = os.path.join(extract_dir, "annotated")
    review_data = session.get("review_data", {})
    for fname, data in review_data.items():
        orig = data.get("annotated_path")
        if orig:
            new_path = os.path.join(ann_dir, os.path.basename(orig))
            data["annotated_path"] = new_path if os.path.exists(new_path) else None

    schema_txt = ""
    schema_path = os.path.join(extract_dir, "schema.txt")
    if os.path.exists(schema_path):
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_txt = f.read()

    return {
        "name": name,
        "folder": extract_dir,
        "invoice_files": session.get("invoice_files", []),
        "review_data": review_data,
        "schema": schema_txt,
    }


def delete_session(zip_path, folder_path):
    if zip_path and os.path.exists(zip_path):
        try:
            os.remove(zip_path)
        except Exception as e:
            print(f"[session] could not delete zip: {e}")
    if folder_path and os.path.exists(folder_path):
        try:
            shutil.rmtree(folder_path)
        except Exception as e:
            print(f"[session] could not delete folder: {e}")