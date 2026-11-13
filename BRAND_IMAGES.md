# AURK artwork

Your supplied files are installed unchanged:
- `app/static/images/brand/logo.jpeg`: original square logo. Header and admin use CSS framing to display its exact lettering; footer displays the complete emblem.
- `app/static/images/brand/hero.png`: original homepage banner (2073 x 759).
- Optional `app/static/images/brand/hero-mobile.jpg`: portrait mobile banner, recommended 1080 x 1440.

Replace these files and press Ctrl+F5 to refresh. On hosting, upload them and reload the application. Keep the same logo composition when replacing the square JPEG; for different artwork adjust `.aurk-artwork-square` at the end of `app/static/css/aurk.css`.

The exact custom lettering is displayed from your image. A JPEG does not provide an installable font for ordinary text, which now spells the brand AURK.

Edit homepage headings in `app/templates/pages/home.html`. Product photos remain managed through admin. Do not include headings/buttons in new banner photos because the website already renders them.
