# Compatibility shim — this module is referenced by migrations only.
# The Bin model was superseded by Bins (bins.py).
from app.utils.comfun import generate_unique_id


def generate_bin_id():
    return f"BIN-{generate_unique_id()}"
