# AURK QA discovery and test inventory

Local repository only. No AWS, public-site, or SMTP access.

## Routes

| Methods | URL | Endpoint | Access |
|---|---|---|---|
| GET | `/` | `main.home` | Public / conditional |
| GET | `/about` | `main.about` | Public / conditional |
| GET | `/account` | `orders.dashboard` | Customer login |
| GET | `/account/` | `orders.dashboard` | Customer login |
| POST | `/account/address` | `orders.update_address` | Customer login |
| GET | `/account/orders` | `orders.list_orders` | Customer login |
| GET | `/account/orders/<order_number>` | `orders.detail` | Customer login |
| GET | `/account/orders/<order_number>/status` | `orders.status` | Customer login |
| POST | `/account/profile` | `orders.update_profile` | Customer login |
| GET | `/admin` | `admin.legacy_dashboard` | Admin session |
| GET | `/admin/` | `admin.legacy_dashboard` | Admin session |
| GET | `/admin/analytics` | `admin.analytics` | Admin session + analytics.view |
| GET | `/admin/categories` | `admin.categories` | Admin session + products.update |
| POST | `/admin/categories/<int:category_id>/delete` | `admin.delete_category` | Admin session + products.delete |
| GET, POST | `/admin/categories/<int:category_id>/edit` | `admin.edit_category` | Admin session + products.update |
| GET, POST | `/admin/categories/create` | `admin.edit_category` | Admin session + products.update |
| GET | `/admin/coupons` | `admin.coupons` | Admin session + coupons.manage |
| POST | `/admin/coupons/<int:coupon_id>/<action>` | `admin.coupon_action` | Admin session + coupons.manage |
| GET, POST | `/admin/coupons/<int:coupon_id>/edit` | `admin.edit_coupon` | Admin session + coupons.manage |
| GET, POST | `/admin/coupons/create` | `admin.edit_coupon` | Admin session + coupons.manage |
| GET | `/admin/customers` | `admin.customers` | Admin session + customers.manage |
| GET, POST | `/admin/customers/<int:user_id>` | `admin.customer_detail` | Admin session + customers.manage |
| GET | `/admin/dashboard` | `admin.dashboard` | Admin session + dashboard.view |
| GET | `/admin/interests` | `admin.interests` | Admin session + customers.manage |
| GET | `/admin/inventory` | `admin.inventory` | Admin session + inventory.manage |
| POST | `/admin/inventory/<int:variant_id>` | `admin.update_inventory` | Admin session + inventory.manage |
| GET, POST | `/admin/login` | `admin.login` | Public / conditional |
| POST | `/admin/logout` | `admin.logout` | Admin session |
| GET | `/admin/orders` | `admin.orders` | Admin session + orders.manage |
| GET | `/admin/orders/<order_number>` | `admin.order_detail` | Admin session + orders.manage |
| POST | `/admin/orders/<order_number>/confirm` | `admin.confirm_order` | Admin session + orders.manage |
| POST | `/admin/orders/<order_number>/payment-received` | `admin.record_order_payment` | Admin session + orders.manage |
| POST | `/admin/orders/<order_number>/retry-alerts` | `admin.retry_order_alerts` | Admin session + orders.manage |
| POST | `/admin/orders/<order_number>/status` | `admin.update_order_status` | Admin session + orders.manage |
| GET | `/admin/product-images/<int:image_id>` | `admin.product_image` | Admin session + products.view |
| GET | `/admin/products` | `admin.products` | Admin session + products.view |
| POST | `/admin/products/<int:product_id>/delete` | `admin.delete_product` | Admin session + products.delete |
| GET, POST | `/admin/products/<int:product_id>/edit` | `admin.edit_product` | Admin session + products.update |
| POST | `/admin/products/<int:product_id>/images/<int:image_id>/delete` | `admin.delete_product_image` | Admin session + products.update |
| POST | `/admin/products/<int:product_id>/images/<int:image_id>/primary` | `admin.set_primary_image` | Admin session + products.update |
| POST | `/admin/products/<int:product_id>/variants` | `admin.create_variant` | Admin session + products.update |
| POST | `/admin/products/<int:product_id>/variants/<int:variant_id>` | `admin.update_variant` | Admin session + products.update |
| GET, POST | `/admin/products/create` | `admin.create_product` | Admin session + products.create |
| GET | `/admin/reports/<kind>.csv` | `admin.export_report` | Admin session + analytics.view |
| GET | `/admin/reviews` | `admin.reviews` | Admin session + reviews.manage |
| POST | `/admin/reviews/<int:review_id>` | `admin.moderate_review` | Admin session + reviews.manage |
| GET, POST | `/admin/settings` | `admin.settings` | Admin session + settings.manage |
| GET | `/admin/worn-by-you` | `admin.worn_by_you` | Admin session + reviews.manage |
| POST | `/admin/worn-by-you/<int:photo_id>` | `admin.moderate_customer_photo` | Admin session + reviews.manage |
| GET | `/api/health` | `api.health` | Public / conditional |
| GET, POST | `/auth/forgot-password` | `auth.forgot_password` | Public / conditional |
| GET, POST | `/auth/login` | `auth.login` | Public / conditional |
| POST | `/auth/logout` | `auth.logout` | Customer login |
| GET, POST | `/auth/register` | `auth.register` | Public / conditional |
| GET, POST | `/auth/reset-password/<token>` | `auth.reset_password` | Public / conditional |
| GET | `/cart` | `cart.view` | Public / conditional |
| POST | `/cart/add` | `cart.add` | Public / conditional |
| POST | `/cart/remove` | `cart.remove` | Public / conditional |
| POST | `/cart/update` | `cart.update` | Public / conditional |
| GET, POST | `/checkout` | `checkout.checkout` | Customer login |
| GET | `/checkout/success/<order_number>` | `checkout.success` | Customer login |
| GET | `/contact` | `main.contact` | Public / conditional |
| GET | `/media/<path:key>` | `main.media` | Public product: public; hidden: authorized admin |
| GET | `/privacy` | `main.privacy` | Public / conditional |
| GET | `/product-image/<int:image_id>` | `products.product_image` | Public product: public; hidden: authorized admin |
| GET | `/product/<slug>` | `products.detail` | Public / conditional |
| POST | `/products/<int:product_id>/interest` | `products.register_interest` | Coming-soon: login; out-of-stock: guest or login |
| GET | `/refund-policy` | `main.refund_policy` | Public / conditional |
| GET | `/returns` | `main.returns` | Public / conditional |
| GET | `/search` | `products.search` | Public / conditional |
| GET | `/shipping` | `main.shipping` | Public / conditional |
| GET | `/shop` | `products.shop` | Public / conditional |
| GET | `/static/<path:filename>` | `static` | Public / conditional |
| GET | `/terms` | `main.terms` | Public / conditional |
| GET | `/worn-by-you` | `community.gallery` | Public / conditional |
| POST | `/worn-by-you/<int:photo_id>/withdraw` | `community.withdraw` | Customer login |
| GET | `/worn-by-you/photos/<int:photo_id>` | `community.photo` | Approved: public; other: owner or reviews.manage admin |
| POST | `/worn-by-you/upload` | `community.upload` | Customer login |

## Models and relationships

### addresses

id: BIGINT required; user_id: BIGINT required; label: VARCHAR(50); recipient_name: VARCHAR(200) required; phone: VARCHAR(30) required; line1: VARCHAR(255) required; line2: VARCHAR(255); city: VARCHAR(100) required; state: VARCHAR(100) required; postal_code: VARCHAR(20) required; country: VARCHAR(100) required; is_default: BOOLEAN required

Relationships: 

Foreign keys: user_id → users.id; delete=CASCADE

### admin_sessions

id: BIGINT required; user_id: BIGINT required; token_hash: VARCHAR(64) required; password_fingerprint: VARCHAR(64) required; created_at: DATETIME required; last_seen_at: DATETIME required; expires_at: DATETIME required

Relationships: 

Foreign keys: user_id → users.id; delete=CASCADE

### audit_logs

id: BIGINT required; actor_user_id: BIGINT; action: VARCHAR(120) required; entity_type: VARCHAR(80); entity_id: VARCHAR(100); ip_address: VARCHAR(45); user_agent: VARCHAR(500); details: JSON; created_at: DATETIME required

Relationships: 

Foreign keys: actor_user_id → users.id; delete=SET NULL

### cart_items

id: BIGINT required; cart_id: BIGINT required; variant_id: BIGINT required; quantity: INTEGER required

Relationships: cart → carts (one); variant → product_variants (one)

Foreign keys: cart_id → carts.id; delete=CASCADE; variant_id → product_variants.id; delete=RESTRICT

### carts

id: BIGINT required; user_id: BIGINT required; coupon_code: VARCHAR(100)

Relationships: items → cart_items (many)

Foreign keys: user_id → users.id; delete=CASCADE

### categories

id: BIGINT required; name: VARCHAR(120) required; slug: VARCHAR(140) required; description: TEXT; is_active: BOOLEAN required; sort_order: INTEGER required

Relationships: products → products (many)

Foreign keys: 

### colors

id: BIGINT required; name: VARCHAR(50) required; hex_code: VARCHAR(7)

Relationships: 

Foreign keys: 

### coupon_usages

id: BIGINT required; coupon_id: BIGINT required; user_id: BIGINT required; order_id: BIGINT required; used_at: DATETIME required

Relationships: 

Foreign keys: order_id → orders.id; delete=RESTRICT; coupon_id → coupons.id; delete=RESTRICT; user_id → users.id; delete=RESTRICT

### coupons

id: BIGINT required; code: VARCHAR(80) required; discount_type: VARCHAR(20) required; value: NUMERIC(12, 2) required; minimum_order: NUMERIC(12, 2) required; maximum_discount: NUMERIC(12, 2); starts_at: DATETIME required; expires_at: DATETIME required; usage_limit: INTEGER; per_user_limit: INTEGER; usage_count: INTEGER required; is_active: BOOLEAN required

Relationships: 

Foreign keys: 

### customer_emails

id: BIGINT required; event_key: VARCHAR(100) required; kind: VARCHAR(30) required; user_id: BIGINT required; order_id: BIGINT; interest_id: BIGINT; recipient: VARCHAR(255) required; status: VARCHAR(20) required; attempts: INTEGER required; next_attempt_at: DATETIME required; created_at: DATETIME required; submitted_at: DATETIME; last_error: VARCHAR(200)

Relationships: customer → users (one); order → orders (one); interest → product_interests (one)

Foreign keys: user_id → users.id; delete=CASCADE; interest_id → product_interests.id; delete=SET NULL; order_id → orders.id; delete=CASCADE

### customer_photos

id: BIGINT required; user_id: BIGINT required; product_id: BIGINT required; order_item_id: BIGINT required; storage_key: VARCHAR(500) required; caption: VARCHAR(400) required; status: VARCHAR(20) required; created_at: DATETIME required

Relationships: customer → users (one); product → products (one); order_item → order_items (one)

Foreign keys: order_item_id → order_items.id; delete=CASCADE; product_id → products.id; delete=RESTRICT; user_id → users.id; delete=CASCADE

### inventory

id: BIGINT required; variant_id: BIGINT required; quantity: INTEGER required; reserved_quantity: INTEGER required; low_stock_threshold: INTEGER required; updated_at: DATETIME required

Relationships: variant → product_variants (one)

Foreign keys: variant_id → product_variants.id; delete=CASCADE

### inventory_movements

id: BIGINT required; variant_id: BIGINT required; quantity_delta: INTEGER required; reason: VARCHAR(100) required; reference: VARCHAR(100); created_by: BIGINT; created_at: DATETIME required

Relationships: 

Foreign keys: created_by → users.id; delete=SET NULL; variant_id → product_variants.id; delete=RESTRICT

### order_items

id: BIGINT required; order_id: BIGINT required; variant_id: BIGINT required; product_name_snapshot: VARCHAR(255) required; sku_snapshot: VARCHAR(100) required; size_snapshot: VARCHAR(50) required; color_snapshot: VARCHAR(80) required; unit_price: NUMERIC(12, 2) required; discount: NUMERIC(12, 2) required; tax: NUMERIC(12, 2) required; quantity: INTEGER required; line_total: NUMERIC(12, 2) required

Relationships: order → orders (one)

Foreign keys: variant_id → product_variants.id; delete=RESTRICT; order_id → orders.id; delete=CASCADE

### order_notifications

id: BIGINT required; order_id: BIGINT required; channel: VARCHAR(20) required; status: VARCHAR(20) required; attempts: INTEGER required; last_error: VARCHAR(255); submitted_at: DATETIME

Relationships: order → orders (one)

Foreign keys: order_id → orders.id; delete=CASCADE

### orders

id: BIGINT required; user_id: BIGINT required; order_number: VARCHAR(40) required; status: VARCHAR(40) required; subtotal: NUMERIC(12, 2) required; discount: NUMERIC(12, 2) required; shipping: NUMERIC(12, 2) required; tax: NUMERIC(12, 2) required; total: NUMERIC(12, 2) required; currency: VARCHAR(3) required; shipping_name: VARCHAR(200) required; shipping_phone: VARCHAR(30) required; shipping_line1: VARCHAR(255) required; shipping_line2: VARCHAR(255); shipping_city: VARCHAR(100) required; shipping_state: VARCHAR(100) required; shipping_postal_code: VARCHAR(20) required; shipping_country: VARCHAR(100) required; created_at: DATETIME required; updated_at: DATETIME required

Relationships: items → order_items (many); payments → payments (many); notifications → order_notifications (many)

Foreign keys: user_id → users.id; delete=RESTRICT

### payments

id: BIGINT required; order_id: BIGINT required; provider: VARCHAR(50) required; provider_order_id: VARCHAR(255) required; provider_payment_id: VARCHAR(255); status: VARCHAR(40) required; amount: NUMERIC(12, 2) required; currency: VARCHAR(3) required; paid_at: DATETIME; created_at: DATETIME required

Relationships: order → orders (one)

Foreign keys: order_id → orders.id; delete=RESTRICT

### permissions

id: BIGINT required; name: VARCHAR(100) required

Relationships: roles → roles (many)

Foreign keys: 

### product_images

id: BIGINT required; product_id: BIGINT required; storage_key: VARCHAR(500) required; mime_type: VARCHAR(100) required; file_size: BIGINT required; width: INTEGER required; height: INTEGER required; sort_order: INTEGER required; is_primary: BOOLEAN required

Relationships: product → products (one)

Foreign keys: product_id → products.id; delete=CASCADE

### product_interests

id: BIGINT required; product_id: BIGINT required; customer_id: BIGINT; identity_key: VARCHAR(80) required; customer_name: VARCHAR(200); customer_email: VARCHAR(254); customer_phone: VARCHAR(30); product_status: VARCHAR(20) required; created_at: DATETIME required; notified_at: DATETIME

Relationships: product → products (one)

Foreign keys: customer_id → users.id; delete=SET NULL; product_id → products.id; delete=CASCADE

### product_specifications

id: BIGINT required; product_id: BIGINT required; name: VARCHAR(100) required; value: VARCHAR(500) required

Relationships: product → products (one)

Foreign keys: product_id → products.id; delete=CASCADE

### product_tags

product_id: BIGINT required; tag_id: BIGINT required

Relationships: 

Foreign keys: product_id → products.id; delete=CASCADE; tag_id → tags.id; delete=CASCADE

### product_variants

id: BIGINT required; product_id: BIGINT required; size_id: BIGINT required; color_id: BIGINT required; sku: VARCHAR(100) required; price_override: NUMERIC(12, 2); is_active: BOOLEAN required

Relationships: product → products (one); size → sizes (one); color → colors (one); inventory → inventory (one)

Foreign keys: size_id → sizes.id; delete=RESTRICT; color_id → colors.id; delete=RESTRICT; product_id → products.id; delete=CASCADE

### products

product_status: VARCHAR(20) required; hide_price: BOOLEAN required; id: BIGINT required; category_id: BIGINT; name: VARCHAR(255) required; slug: VARCHAR(280) required; description: TEXT required; base_price: NUMERIC(12, 2) required; sale_price: NUMERIC(12, 2); is_archived: BOOLEAN required; is_active: BOOLEAN required; is_featured: BOOLEAN required; is_new_arrival: BOOLEAN required; is_bestseller: BOOLEAN required; seo_title: VARCHAR(255); seo_description: TEXT; created_at: DATETIME required; updated_at: DATETIME required

Relationships: interests → product_interests (many); category → categories (one); images → product_images (many); variants → product_variants (many); specifications → product_specifications (many); tags → tags (many)

Foreign keys: category_id → categories.id; delete=SET NULL

### reviews

id: BIGINT required; user_id: BIGINT required; product_id: BIGINT required; rating: SMALLINT required; body: TEXT required; is_approved: BOOLEAN required; verified_purchase: BOOLEAN required; created_at: DATETIME required

Relationships: product → products (one); customer → users (one)

Foreign keys: user_id → users.id; delete=RESTRICT; product_id → products.id; delete=CASCADE

### roles

id: BIGINT required; name: VARCHAR(50) required

Relationships: permissions → permissions (many); users → users (many)

Foreign keys: 

### sizes

id: BIGINT required; name: VARCHAR(30) required

Relationships: 

Foreign keys: 

### tags

id: BIGINT required; name: VARCHAR(80) required

Relationships: products → products (many)

Foreign keys: 

### users

id: BIGINT required; email: VARCHAR(255) required; password_hash: VARCHAR(255) required; first_name: VARCHAR(100) required; last_name: VARCHAR(100) required; phone: VARCHAR(30); is_active: BOOLEAN required; created_at: DATETIME required; updated_at: DATETIME required

Relationships: roles → roles (many)

Foreign keys: 

### wishlist_items

id: BIGINT required; wishlist_id: BIGINT required; product_id: BIGINT required

Relationships: wishlist → wishlists (one); product → products (one)

Foreign keys: product_id → products.id; delete=CASCADE; wishlist_id → wishlists.id; delete=CASCADE

### wishlists

id: BIGINT required; user_id: BIGINT required

Relationships: items → wishlist_items (many)

Foreign keys: user_id → users.id; delete=CASCADE

## Service functions

- `app/services/addresses.py`: validate_shipping_details:6
- `app/services/catalog.py`: price_bounds:5, prepare_storefront_products:12, storefront_price_expression:19
- `app/services/coupons.py`: validate_coupon:5
- `app/services/customer_email_templates.py`: render_customer_order_email:34, _public_origin:50, render_customer_welcome_email:59, render_customer_interest_email:74
- `app/services/customer_emails.py`: queue_customer_email:14, send_rendered_email:24, queue_interest_acknowledgement:30, dispatch_customer_emails:43, send_customer_emails_command:99, send_email_test_command:118
- `app/services/customer_photos.py`: save_customer_photo:11
- `app/services/email.py`: send_email:8
- `app/services/guest_cart.py`: contents:13, save:17, guest_cart:24, merge_into_account:36
- `app/services/image_storage.py`: save_product_image:11
- `app/services/inventory.py`: available_stock:4, reserve_variant:6
- `app/services/order_notifications.py`: queue_order_alerts:18, order_review_url:26, alert_values:34, send_whatsapp:42, dispatch_order_alerts:69, send_order_alerts_command:111
- `app/services/order_status.py`: change_status:13, record_cod_received:54
- `app/services/payments.py`: create_order:5, verify_payment:7, verify_webhook:9, __init__:12, create_order:14, verify_payment:16, verify_webhook:18
- `app/services/pricing.py`: money:5, calculate_subtotal:7, calculate_total:10
- `app/services/product_interests.py`: notify_interest:14, send_interest_alerts_command:45
- `app/services/product_video.py`: boxes:8, save_product_video:28
## Existing test functions

- `tests/integration/test_cod_orders.py`: test_pending_then_owner_confirms_and_customer_sees_status:56, test_other_customer_cannot_read_order_or_status:83, test_invalid_delivery_preserves_fields_and_does_not_place_order:91, test_repeated_checkout_does_not_duplicate_order:101, test_out_of_stock_does_not_place_order:111, test_alert_failure_keeps_order_and_retry_skips_submitted_channel:122, test_disabled_whatsapp_skips_previously_queued_alert:144, test_confirmation_requires_csrf:161, test_whatsapp_template_request_uses_seven_parameters:170, test_alert_cli_runs_in_app_context:185, test_smtp_uses_tls_and_sends_complete_message:190, test_checkout_renders_cod_and_saved_address:211, test_product_displays_variant_price_and_stock:226, test_sold_out_product_has_no_purchase_form:239, test_guest_shops_then_signs_in_at_checkout:248, test_cart_warns_when_stock_changes:276, test_inactive_cart_item_can_be_removed_but_not_updated:291, test_invalid_cart_quantity_is_not_added:307, test_shop_sort_and_filter_controls_render_without_inline_scripts:315, test_guest_cart_update_remove_and_session_isolation:324, test_failed_login_preserves_guest_bag:343, test_registration_keeps_guest_bag_and_checkout_destination:356, test_guest_add_respects_stock_and_csrf:372, test_guest_merge_keeps_changed_stock_visible:384, test_registration_rejects_external_next_url:399, test_homepage_uses_live_catalogue_and_hides_inactive_products:406, test_owner_fulfils_order_without_marking_payment_paid:422, test_cancellation_restores_stock_once_and_stops_alerts:446, test_cancellation_requires_reason_and_rejects_shipped_orders:469, test_status_updates_require_post_and_csrf:484, test_admin_order_filters_and_search:493, test_cancellation_does_not_restore_stock_for_paid_order:502, test_cod_receipt_requires_delivery_and_records_once:516, test_cod_receipt_rejects_mismatched_amount_and_requires_csrf:544, test_collection_create_edit_visibility_and_product_assignment:569, test_collection_rejects_duplicates_and_invalid_sort:592, test_collection_mutations_require_permission_and_csrf:601, test_checkout_rejects_overseas_address:609, test_storefront_sort_matches_available_option_price:616, test_public_pages_render_and_have_no_business_placeholders:629, test_admin_can_create_sellable_product_and_images_are_private_when_hidden:642, test_password_reset_link_cannot_be_reused:674
- `tests/integration/test_commerce.py`: test_cart_adds_the_submitted_variant_not_a_matching_variant:38, test_checkout_creates_an_order_and_reduces_stock:64
- `tests/integration/test_customer_account.py`: test_account_requires_login:29, test_dashboard_empty_and_private:35, test_orders_scoped_and_paginated:43, test_profile_updates_only_allowed_fields:61, test_address_scoped_and_preserves_order_snapshot:75, test_address_validation:92, test_account_forms_require_csrf:97
- `tests/integration/test_customer_email_automation.py`: test_signup_queues_welcome_only_for_successful_registration:26, test_disabled_does_not_queue_or_send:38, test_customer_mail_senders_reply_to_and_no_deliberate_resend:48, test_confirmation_idempotency_and_cancellation:68, test_failure_backoff_and_limited_retry:81, test_cli_and_inactive_customer_skip:97, test_explicit_sample_test_cli_uses_only_selected_inbox:107, test_retry_exhaustion_is_not_resent:115, test_transport_sets_reply_to_header:124, test_inline_logo_embedded_in_html_part:143
- `tests/integration/test_customer_photos.py`: test_gallery_public_upload_requires_signin:52, test_requires_own_delivered_item:59, test_pending_private_approved_public_and_withdrawal:65, test_validation_and_csrf:101, test_limit_and_rejected_photo_private:112
- `tests/integration/test_health.py`: test_health:1
- `tests/integration/test_migrations.py`: test_fresh_database_migrations:6
- `tests/integration/test_product_availability.py`: test_notify_login_return_and_subscription:35, test_notify_acknowledgement_queued_once_and_retried:55, test_business_notify_failure_retried_by_existing_worker:91, test_notify_sample_cli:109, test_unavailable_visible_and_blocked:124, test_registration_duplicate_email_and_reload:155, test_email_failure_saved_and_retryable:189, test_status_transition_and_invalid_product:206, test_database_failure_allows_retry:226, test_csrf_and_product_deletion:239, test_admin_status_and_interest_permissions:254, test_coming_soon_optional_price:276, test_gallery_controls_only_visible_on_product_page:320
- `tests/security/test_admin_workspace.py`: test_every_admin_page_blocks_guest_and_customer:40, test_admin_pages_render_and_storefront_keeps_separate_design:60, test_customer_login_does_not_elevate_even_an_admin:79, test_admin_login_errors_are_generic:87, test_invalid_expired_and_revoked_sessions_are_blocked:95, test_role_and_permission_revocation_take_effect:119, test_disabled_admin_and_changed_password_invalidate_session:134, test_customer_status_and_no_role_mass_assignment:149, test_inventory_validation_and_audit:161, test_category_deletion_preserves_products:173, test_coupon_crud_and_review_moderation:182, test_password_change_requires_current_password_and_revokes_admin_sessions:206, test_csrf_errors_use_admin_layout:217, test_admin_headers_and_safe_redirect:225, test_admin_login_is_rate_limited:236, test_csrf_protects_authenticated_mutations:251, test_registration_cannot_assign_roles_and_invalid_input_is_safe:265, test_hidden_images_require_admin_session:278, test_migration_preserves_users_and_grants_only_owner_role:301, test_admin_option_creation_and_edits_share_inventory:329, test_multiple_product_views_and_size_chart_upload:353, test_bulk_sizes_and_mixed_size_checkout:379, test_delete_stocked_product_removes_it_from_catalogue_but_keeps_history:407, test_hidden_product_remains_editable_until_deleted:425, test_clickable_sizes_generate_skus_without_manual_codes:435, test_product_cards_allow_guest_purchase_without_detail_page:453, test_separate_colour_size_fields_without_option_prices:477, test_one_step_listing_creates_stock_and_unique_links:490, test_percentage_discount_multi_upload_and_store_prices:532, test_dashboard_reports_dates_exports_and_back_navigation:574
- `tests/security/test_auth.py`: test_register_creates_user:5, test_login_with_correct_password:32, test_login_with_wrong_password_fails:62, test_inactive_user_cannot_login:91, test_logout_requires_post:121, test_protected_admin_requires_authentication:127
- `tests/security/test_password_recovery.py`: test_admin_email_reset_and_single_use:29, test_invalid_password_preserves_account:47, test_unknown_email_and_smtp_failure_show_same_confirmation:54, test_invalid_expired_token_and_csrf:63, test_reset_url_uses_configured_domain:72
- `tests/unit/test_customer_email_templates.py`: test_notify_uses_shared_branding_and_escapes_product_name:6, test_order_email_content_and_reply_address:21, test_order_email_escaping_and_optional_fields:44, test_order_email_requires_clean_https_origin:57, test_order_email_rejects_unknown_template_and_header_injection:62, test_welcome_template_is_personalized_and_has_no_secrets:71, test_welcome_escapes_name_and_validates_origin:89, test_black_white_branding_with_uploaded_logo:101, test_all_emails_use_shared_dark_background:114
- `tests/unit/test_pricing.py`: test_money_rounds:4, test_total_never_goes_negative:5
- `tests/unit/test_product_video.py`: test_mp4_storage:16, test_reject_invalid_video:27, test_video_does_not_replace_photo_cover:34, test_gallery_excludes_video_from_photo_slider:44

## Migration chain

- `None` → `11b8ff211bcb`: `migrations/versions/11b8ff211bcb_initial_schema.py`
- `11b8ff211bcb` → `23ab91cd4500`: `migrations/versions/23ab91cd4500_order_alerts.py`
- `23ab91cd4500` → `34cd72ef5610`: `migrations/versions/34cd72ef5610_admin_workspace.py`
- `34cd72ef5610` → `45de83fa6721`: `migrations/versions/45de83fa6721_archive_products.py`
- `45de83fa6721` → `56ef94ab7832`: `migrations/versions/56ef94ab7832_product_availability.py`
- `56ef94ab7832` → `67fa05bc8943`: `migrations/versions/67fa05bc8943_coming_soon_price.py`
- `67fa05bc8943` → `78ab16cd9054`: `migrations/versions/78ab16cd9054_customer_photos.py`
- `78ab16cd9054` → `89bc27de0165`: `migrations/versions/89bc27de0165_customer_email_outbox.py`
- `89bc27de0165` → `90cd38ef1276`: `migrations/versions/90cd38ef1276_notify_interest_emails.py`

## Feature test inventory

| Feature | Existing coverage | Audit additions / evidence |
|---|---|---|
| Catalog | Public pages, sorting, pricing, gallery, availability | Search/filter fuzzing, archived visibility, N+1 and timing, broken assets |
| Cart | Guest persistence/merge, variant identity, stock checks | Quantity matrix, client price tampering, cross-customer mutation |
| Accounts | Login, signup, password recovery, profile/address | Normalization, session revocation after password reset, redirect controls, rate limits |
| Checkout | COD happy path, address checks, stock changes | Forced transaction failure, stale prices, duplicate submit, dedicated MySQL last-unit race |
| Orders | Transitions, cancellation, payment receipt | Full invalid transition matrix and audit checks |
| Admin | Sessions, some permissions, CRUD, reports | Every route by actor/permission and CSRF enumeration |
| Emails | Branding, retries, deduplication, sender/Reply-To | Concurrent workers, SMTP acceptance ambiguity, injection and deleted interest |
| Notify me | Guest gate, duplicates, owner/customer alerts | Restock limitation documented; no real SMTP |
| Worn by you | Ownership/delivery/consent/moderation | Malicious filenames, metadata, corrupt/large photos and private URLs |
| Security | Selected CSRF, admin deny, password reset | All mutation routes, IDOR, headers, gitignore, secret scanning |
| Migrations | Fresh SQLite upgrade | Latest downgrade/upgrade, metadata comparison; MySQL blocked until safe URL |
| Frontend | Server-rendered HTML checks | Approved Chromium desktop/mobile journeys, console, axe accessibility, layout |
| Deployment | Existing documentation | Static-only config audit, no production connection |

## Configuration differences

Development: DEBUG on. Production: DEBUG/TESTING off; Secure cookies default on but environment can override. Testing: in-memory SQLite by default, CSRF and limiter disabled, SMTP host blank, secret has a test default. Upload directory and email-enable flag otherwise inherit environment; the QA fixtures explicitly isolate/disable these. Dedicated MySQL must be local and have test/qa in its schema name.

Per-test database tables are recreated for request tests because application code commits internally; this tests actual commit/rollback behavior rather than hiding commits inside a test transaction.
