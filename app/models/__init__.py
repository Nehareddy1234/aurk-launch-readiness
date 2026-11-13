from .storefront import StorefrontContent
from .fulfilment import StoreSettings, Shipment, CodSettlement
from .customer_email import CustomerEmail
from .customer_photo import CustomerPhoto
from .admin_session import AdminSession
from .user import User, Role, Permission

from .catalog import (
    Category,
    Product,
    Size,
    Color,
    ProductVariant,
    ProductImage,
    Tag,
    ProductTag,
    ProductSpecification,
)

from .commerce import (
    Cart,
    CartItem,
    Address,
    Order,
    OrderItem,
    Payment,
    OrderNotification,
)

from .engagement import (
    ProductInterest,
    Wishlist,
    WishlistItem,
    Review,
)

from .promotion import (
    Coupon,
    CouponUsage,
)

from .operations import (
    Inventory,
    InventoryMovement,
    AuditLog,
)


def register_models():
    """
    Import all SQLAlchemy models so that they are
    registered with the SQLAlchemy metadata.
    """

    return True
