from app.extensions import db


class StorefrontContent(db.Model):
    __tablename__ = "storefront_content"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.JSON, nullable=False)
