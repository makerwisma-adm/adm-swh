"""Upload file helpers."""
import os

from app.config import UPLOAD_DIR

def _delete_upload_file(rel_path: str):
    if not rel_path:
        return
    full = os.path.join(UPLOAD_DIR, rel_path)
    if os.path.isfile(full):
        try:
            os.remove(full)
        except OSError:
            pass


def _delete_nota_file(nota_path: str):
    _delete_upload_file(nota_path)
