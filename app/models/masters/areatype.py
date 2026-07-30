"""Historical migration compatibility for the removed AreaType model."""

from app.utils.comfun import generate_unique_id


def generate_area_type_id():
    return f"AREA-{generate_unique_id()}"
