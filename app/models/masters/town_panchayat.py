"""Historical migration compatibility for the removed TownPanchayat model."""

from app.utils.comfun import generate_unique_id


def generate_town_panchayat_id():
    return f"TWNP-{generate_unique_id()}"
