from app.extensions import db
from app.models import Inventory

def available_stock(inventory): return max(0, inventory.quantity - inventory.reserved_quantity)

def reserve_variant(variant, quantity):
    inventory = db.session.execute(db.select(Inventory).where(Inventory.variant_id == variant.id).with_for_update()).scalar_one()
    if available_stock(inventory) < quantity:
        raise ValueError("Insufficient stock.")
    inventory.reserved_quantity += quantity
    return inventory
