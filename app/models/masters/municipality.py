"""Historical migration compatibility for the removed Municipality model."""

from app.utils.comfun import generate_unique_id


def generate_municipality_id():
    return f"MNCPL-{generate_unique_id()}"
