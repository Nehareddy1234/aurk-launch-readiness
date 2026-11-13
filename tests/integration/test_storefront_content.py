from io import BytesIO
from pathlib import Path
from PIL import Image
import pytest
from app.extensions import db
from app.models import StorefrontContent


def form(**changes):
    data = dict(cover_enabled="1", cover_title="QA campaign", cover_subtitle="New drop",
                cover_button="Explore", cover_link="/shop", bar_enabled="1",
                bar_messages="QA discount\nFree delivery", bar_link="/shop", bar_speed="slow")
    for i in range(3):
        data[f"banner_{i}_link"] = "/shop"
    data.update(changes)
    return data


def sign_in(client, qa_factory, permissions=("settings.manage",)):
    user = qa_factory.admin(permissions=permissions)
    assert client.post("/admin/login", data=dict(email=user.email, password="QaPassword123!")).status_code == 302


def image():
    output = BytesIO()
    Image.new("RGB", (120, 60), "red").save(output, "PNG")
    output.seek(0)
    return output


def test_storefront_publishing_and_media_access(app, client, qa_factory):
    assert b"videos/store-cover.mp4" in client.get("/").data
    sign_in(client, qa_factory)
    assert client.get("/admin/storefront").status_code == 200
    data = form(banner_0_enabled="1", banner_0_alt="QA red banner", banner_0_title="QA sale",
                banner_0_image=(image(), "banner.png"))
    assert client.post("/admin/storefront", data=data).status_code == 302
    with app.app_context():
        saved = db.session.get(StorefrontContent, 1).content
        key = saved["banners"][0]["image"]
    home = client.get("/")
    assert home.status_code == 200
    assert b"QA campaign" in home.data and b"QA sale" in home.data
    assert b"promotion-slow" in home.data
    assert client.get("/shop").data.count(b"QA discount") == 2
    media = client.get("/storefront-media/" + key)
    assert media.status_code == 200 and media.mimetype == "image/jpeg"
    assert client.get("/storefront-media/storefront/not-published.jpg").status_code == 404
    assert client.post("/admin/storefront", data=form(banner_0_remove="1")).status_code == 302
    assert client.get("/storefront-media/" + key).status_code == 404


@pytest.mark.parametrize("changes", [dict(cover_link="//evil.example"), dict(bar_link="javascript:alert(1)"),
                                    dict(bar_speed="infinite"), dict(bar_messages=""), dict(banner_0_enabled="1")])
def test_rejected_content_does_not_publish(app, client, qa_factory, changes):
    sign_in(client, qa_factory)
    assert client.post("/admin/storefront", data=form(**changes)).status_code == 400
    with app.app_context():
        assert db.session.get(StorefrontContent, 1) is None


def test_upload_failure_cleans_new_files(app, client, qa_factory):
    sign_in(client, qa_factory)
    data = form(poster=(image(), "poster.png"), banner_0_image=(BytesIO(b"invalid"), "bad.jpg"))
    assert client.post("/admin/storefront", data=data).status_code == 400
    assert list((Path(app.config["UPLOAD_DIR"]) / "storefront").glob("*")) == []


def test_storefront_permissions_and_csrf(app, client, qa_factory):
    assert client.post("/admin/storefront", data=form()).status_code in (302, 403)
    sign_in(client, qa_factory, permissions=("products.view",))
    assert client.get("/admin/storefront").status_code == 403
    assert client.post("/admin/storefront", data=form()).status_code == 403
    app.config["WTF_CSRF_ENABLED"] = True
    assert client.post("/admin/storefront", data=form()).status_code == 400


def test_cover_and_bar_can_be_hidden(client, qa_factory):
    sign_in(client, qa_factory)
    assert client.post("/admin/storefront", data=form(cover_enabled="", bar_enabled="")).status_code == 302
    page = client.get("/").data
    assert b'<section class="aurk-campaign"' not in page
    assert b'<aside class="promotion-bar' not in page


def test_cover_video_upload_and_range_request(app, client, qa_factory):
    from tests.unit.test_product_video import container
    sign_in(client, qa_factory)
    assert client.post("/admin/storefront", data=form(desktop_video=(BytesIO(container()), "cover.mp4"), second_desktop_video=(BytesIO(container()), "second.mp4"))).status_code == 302
    with app.app_context():
        key = db.session.get(StorefrontContent, 1).content["desktop_video"]
        second_key = db.session.get(StorefrontContent, 1).content["second_desktop_video"]
    home = client.get("/").data
    assert home.count(("/storefront-media/" + key).encode()) == 2
    assert home.count(("/storefront-media/" + second_key).encode()) == 2
    assert b"storefront-benefits" not in home
    assert b"autoplay loop" not in home
    assert client.get("/storefront-media/" + second_key).status_code == 200
    video = client.get("/storefront-media/" + key, headers={"Range": "bytes=0-15"})
    assert video.status_code == 206
    assert video.mimetype == "video/mp4" and len(video.data) == 16
