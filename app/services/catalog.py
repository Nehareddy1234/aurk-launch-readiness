from sqlalchemy import func, select
from app.models import Product, ProductVariant, Inventory


def price_bounds(product):
    variants = [v for v in product.variants if v.is_active]
    available = [v for v in variants if v.inventory and v.inventory.quantity > v.inventory.reserved_quantity]
    prices = [v.price_override if v.price_override is not None else product.current_price for v in available or variants]
    return (min(prices), max(prices)) if prices else (product.current_price, product.current_price)


def prepare_storefront_products(products):
    for product in products:
        low, high = price_bounds(product)
        product.storefront_price = low
        product.storefront_price_varies = low != high


def storefront_price_expression():
    price = func.coalesce(ProductVariant.price_override, Product.sale_price, Product.base_price)
    active = select(func.min(price)).select_from(ProductVariant).where(
        ProductVariant.product_id == Product.id, ProductVariant.is_active.is_(True)).correlate(Product)
    available = active.join(Inventory, Inventory.variant_id == ProductVariant.id).where(
        Inventory.quantity > Inventory.reserved_quantity)
    return func.coalesce(available.scalar_subquery(), active.scalar_subquery(), Product.sale_price, Product.base_price)
