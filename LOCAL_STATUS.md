# AR Drips local website status

Updated: 8 September 2026.

## Implemented

- Public storefront, collections, product galleries and option selection, responsive page styles, navigation and contact links.
- Guest bag with sign-in at checkout, account-cart merging, registration, login, logout and single-use password reset links.
- India-only checkout, free delivery, cash on delivery, stock validation and order creation.
- Owner confirmation, shipped/delivered status, cancellation before shipment with stock restoration, and explicit COD receipt recording.
- Product/image/SKU/inventory and collection management, order search, status filters and audit history.
- Shipping, returns/exchanges, refunds, privacy and terms pages linked from the footer; policy links are also available at checkout.
- The policies use AR Drips and the approved public support contacts, without adding a personal owner name or business address.

## Agreed store rules

- Free delivery across India; estimated 3-5 business days after confirmation.
- Returns and exchanges requested within 5 days after delivery; unused, unwashed items with original tags.
- Customer pays return shipping. Refunds through UPI or cash within 3-5 business days after receipt and inspection.
- Returns, exchanges and refunds are arranged through the public support contacts; the website does not initiate transfers or automate refund payments.

## Verification

- 77 automated tests pass, including guest checkout/account merging, stock and order lifecycle, permissions and CSRF, COD receipts, collections, product/image creation, catalogue pricing and sorting, policy-page rendering, and reset-link reuse prevention.
- All templates compile and JavaScript passes its syntax check.
- Homepage, both price-sort directions, Privacy and Terms return HTTP 200 against the configured local database.
- No real orders, customer payment records or stock were changed for final testing. Automated tests use their isolated testing database and mocked email where needed.
- Visual desktop/mobile inspection could not be completed: the computer-use tool reported no available browsers. Responsive styles are implemented; rendered appearance still needs visual confirmation.

## Outside this local completion scope

Hosting, domains, HTTPS/public URL setup, public order-alert links, and live WhatsApp Business API activation. SMTP email sending was previously verified; automatic owner order-alert links still depend on a public URL. No payment gateway was added.

## Policy reference

The consumer-rights clause preserves applicable remedies rather than treating the store's discretionary returns policy as a waiver. Reference: [Department of Consumer Affairs: Consumer Protection (E-Commerce) Rules, 2020](https://consumeraffairs.nic.in/sites/default/files/E%20commerce%20rules_0.pdf).


## Storefront design update

The customer-facing pages now use a dedicated premium.css stylesheet: warm ivory, charcoal, muted olive, editorial headings, consistent form styling, and responsive product imagery. Admin styling is scoped separately. motion.js adds one-time viewport reveals, menu opening animation and reduced-motion support; content remains visible without JavaScript. No external fonts, animation libraries or third-party assets were added. Visual inspection is still pending a connected browser.


## Separate admin workspace completed (8 September 2026)

- Dedicated `/admin/login` and `/admin/dashboard`, separate monochrome sidebar and responsive layout. Storefront branding remains intact, with admin navigation removed.
- Existing users/roles are reused; admin sign-in additionally establishes a database-backed, revocable session with 30-minute idle and 8-hour absolute expiry. Active roles and individual permissions are checked server-side.
- Products/categories/orders retained; customers, inventory, coupon configuration, review moderation, analytics and profile/security settings connect to the existing database.
- Migration `34cd72ef5610` applied to local MySQL and existing data counts verified unchanged. No new administrator account is needed.
- All 77 tests pass. JavaScript syntax and dependency consistency checks pass. Patched Pillow, cryptography and pytest; final pip-audit reports no known vulnerabilities.
- Browser visual review remains unavailable. Coupon redemption and customer review submission are not existing storefront features and were not added by the admin separation; manual refunds remain outside the payment backend.
- Full handover: [ADMIN_WORKSPACE.md](ADMIN_WORKSPACE.md). Restart the local server and sign in at `/admin/login` with the existing admin account.


## Logo branding and product photography

The supplied original transparent AR Drips logo is stored at `app/static/images/ar-drips-logo.png` and used in the storefront header/footer, admin sidebar/login and browser favicon. The storefront palette now uses navy, blue and cyan on light blue-white surfaces; premium spacing and reduced-motion-aware animation remain. The admin workspace retains neutral operational styling with the original logo on white for readability.

Product images fit 4:5 portrait frames using `object-fit: contain`, preserving the full photo without distortion. Home/catalogue hover zoom is disabled to prevent edge cropping. Thumbnails, cart images and admin previews also contain their images. Originals are preserved; this is display fitting, not automatic file compression.

Recommended uploads: 1200 x 1500 pixels, JPG/WEBP (PNG accepted), around 200-500 KB each, up to ten images and under 8 MB combined per upload. Leave space around garments and use consistent backgrounds. These instructions appear in the product editor.

After creating a product, admin opens its editor with a prompt to add size/colour SKUs and opening stock. An automated integration test verifies that adding a SKU creates inventory and that both product-editor stock changes and inventory-page changes update the same record, with the correct inventory movement deltas.

Validation after logo/inventory updates: **78 tests passed in 101.80 seconds**. Local home, shop, admin login and logo asset requests returned 200. Browser visual review remains unavailable.


## Readability, product views and category access

Raised storefront body text to 17px, primary navigation/buttons to 16px, and small labels to at least 14px. Admin labels/table text are larger too. Product photos can be opened at full size from the gallery, and switching thumbnails updates that link. Multiple-file upload instructions explicitly include front/back/side/detail and size-chart images. The category creation shortcut is visible on the admin overview, and the existing owner role's category permission was verified.


## Size selection and per-size inventory

Storefront size/colour options now appear as selectable buttons with stock-aware availability and quantity +/- controls. The native selector remains the fallback without JavaScript. Different sizes are added separately to the same bag; the cart has an explicit Add another size or colour link. Each SKU retains its own quantity through checkout.

Admin > Products > Edit > Add sizes and colour accepts comma-separated sizes (up to 20), one colour, a SKU prefix, and opening stock per size. Each gets an independent inventory record; duplicate size/colour combinations are rejected and the whole batch rolls back on validation failure. Existing single-size submissions remain compatible. Existing live product stock and sizes were not fabricated or changed.


## Product removal correction

Migration `45de83fa6721` adds `products.is_archived` to distinguish deletion from temporary hiding. Deleting products with historical order or stock records now marks them inactive/archived and excludes them from admin catalogue and inventory lists. Archived products cannot be edited or restocked through normal management routes. Historical order/inventory records remain intact. Ordinary hidden products remain editable. Existing hidden products were not automatically archived because they may have been intentionally hidden; use Delete again to remove them from the list.


## Click-to-add sizes and automatic SKUs

The product editor now offers clickable XS/S/M/L/XL/XXL/3XL/4XL/One size checkboxes. Select several, enter colour and stock per size, then Add sizes. Unique SKU codes are generated server-side automatically; existing codes and stock are preserved. Custom sizing and price overrides are tucked under optional settings. Native checkboxes work without JavaScript. Older manual SKU form submissions remain compatible, but new size-picker submissions always generate their own codes.


## Purchase directly from product cards

Homepage and shop/search cards share a quick-add form: size/colour, quantity, selected price/availability and Add to bag. Only active in-stock variants can be chosen; sold-out products display an unavailable message. Forms use the existing CSRF-protected cart endpoint and support guests, with current server-side price/stock validation. No product-detail visit is required; the image/title links still open details if wanted. Native forms also work without JavaScript.


## Separate size and colour selection

Homepage/shop cards and product detail share independent Colour and Size controls. Available sizes follow the chosen colour and resolve to the exact existing variant ID. Prices are displayed outside options, and server-side cart validation remains unchanged. Without JavaScript a native combined selector remains as a fallback, also without prices. Inspected product photo/size chart originals, verified active catalogue image dimensions and decoding, and changed image frames to white to match uploaded backgrounds. Contain fitting and full-size links preserve square size charts without cropping.
