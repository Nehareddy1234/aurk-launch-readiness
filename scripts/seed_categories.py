from app import create_app
from app.extensions import db
from app.models import Category

app = create_app("development")

categories = [
    {
        "name": "Printed T-Shirts",
        "slug": "printed-t-shirts",
        "description": "Trendy printed T-shirts with unique designs.",
        "sort_order": 1,
    },
    {
        "name": "Oversized T-Shirts",
        "slug": "oversized-t-shirts",
        "description": "Comfortable and stylish oversized printed T-shirts.",
        "sort_order": 2,
    },
    {
        "name": "Graphic T-Shirts",
        "slug": "graphic-t-shirts",
        "description": "Bold graphic designs for everyday streetwear.",
        "sort_order": 3,
    },
    {
        "name": "Anime T-Shirts",
        "slug": "anime-t-shirts",
        "description": "Anime-inspired printed T-shirts.",
        "sort_order": 4,
    },
    {
        "name": "Couple T-Shirts",
        "slug": "couple-t-shirts",
        "description": "Matching and couple-themed T-shirts.",
        "sort_order": 5,
    },
    {
        "name": "Custom T-Shirts",
        "slug": "custom-t-shirts",
        "description": "Custom printed T-shirts made for your ideas.",
        "sort_order": 6,
    },
]

with app.app_context():
    added = 0

    for data in categories:
        existing = Category.query.filter_by(slug=data["slug"]).first()

        if existing:
            print(f"Already exists: {data['name']}")
            continue

        category = Category(
            name=data["name"],
            slug=data["slug"],
            description=data["description"],
            sort_order=data["sort_order"],
            is_active=True,
        )

        db.session.add(category)
        added += 1

    db.session.commit()

    print(f"\nCategories added: {added}")
    print(f"Total categories: {Category.query.count()}")