# AURK tester access and page map

Target: https://aurk.in
Prepared: 24 October 2026

## Access status

No test accounts have been created by this handoff. The workspace database is local and separate from the live website. Account availability and features must be verified against the deployed build.

Provide two dedicated customer accounts and one dedicated test administrator. Share passwords privately, not in this file or Git. Use controlled email inboxes if password reset or email delivery will be tested. Do not share the owner's personal administrator account.

| Account | Purpose | Status |
|---|---|---|
| Customer A | Shopping, account, orders and password recovery | Pending live creation |
| Customer B | Independent shopping session and order privacy checks | Pending live creation |
| Test administrator | Product, inventory, order and moderation checks | Pending live creation |

## Customer page map

| Page / flow | URL |
|---|---|
| Home | https://aurk.in/ |
| Shop, search and available filters | https://aurk.in/shop |
| Product details | Open a product from Shop; URLs depend on product slug |
| Cart | https://aurk.in/cart |
| Checkout | https://aurk.in/checkout |
| Register | https://aurk.in/auth/register |
| Customer login | https://aurk.in/auth/login |
| Password recovery | https://aurk.in/auth/forgot-password |
| Account dashboard | https://aurk.in/account/ |
| Order history | https://aurk.in/account/orders |
| Order detail | Open an order from the signed-in customer's history |
| Customer photo gallery | https://aurk.in/worn-by-you |
| Contact and store policies | Follow the site's footer links |

Main journey: Home -> Shop -> Product/options -> Cart -> Sign in -> Checkout -> Order success -> Account/order history.

## Administrator tools

Sign in at https://aurk.in/admin/login. Use navigation inside the dashboard for Products, Categories, Orders, Customers, Inventory, Analytics, Coupons, Reviews, Worn by you and Settings where available and permitted.

Admin journey: create a QA product and variants -> set test stock -> customer places QA order -> confirm -> ship -> deliver -> simulate COD receipt only if specifically authorized. Test pre-shipment cancellation on a separate QA order.

## What to send the tester

1. This page map and `MANUAL_TESTING_HANDOFF.md`.
2. Website URL and the deployed build/date being tested.
3. Customer A, Customer B and test-admin credentials through a private channel.
4. Agreed testing window, permitted actions, QA product/order identifiers and bug-report contact.
5. Whether email sending is enabled and which controlled inboxes they may use.

No source repository, terminal tools, database access, `.env` or AWS credentials are required for browser-based manual testing. Ask the tester to record browser/device/version and provide screenshots or recordings with bugs.

## Live-store testing boundaries

Begin with public browsing and dedicated customer-account checks. Before test orders, uploads, stock changes, status changes or simulated receipts, agree which QA records may be modified. Keep real customers, inventory, dispatch and payment records outside testing. A staging copy is preferred for destructive and edge-case tests.

Use two independent browser profiles for the two customers. Customer-photo submissions need an authorized delivered QA order. Do not mark a real order delivered just to enable that test. Password recovery and email tests require controlled inboxes; without them, mark those cases blocked.

The owner should deactivate temporary accounts and archive QA products after testing. The application has no established automatic expiry for these test accounts.
