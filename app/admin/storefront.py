from pathlib import Path
from flask import current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user
from app.extensions import db
from app.models import AuditLog, StorefrontContent
from app.security.decorators import permission_required
from app.services.product_video import save_product_video
from app.services.storefront import get_content, local_link, save_image


def register_storefront(bp):
    @bp.route("/storefront", methods=["GET", "POST"])
    @permission_required("settings.manage")
    def storefront():
        content = get_content()
        error = None
        created = []
        if request.method == "POST":
            try:
                def text(name, maximum):
                    value = request.form.get(name, "").strip()
                    if len(value) > maximum:
                        raise ValueError(f"{name.replace('_', ' ').capitalize()} is too long (maximum {maximum} characters).")
                    return value

                for name, maximum in (("cover_title", 100), ("cover_subtitle", 200), ("cover_button", 40), ("bar_messages", 1000)):
                    content[name] = text(name, maximum)
                for name in ("cover_enabled", "bar_enabled"):
                    content[name] = request.form.get(name) == "1"
                for name in ("cover_link", "bar_link"):
                    content[name] = local_link(request.form.get(name, "/shop"))
                content["bar_speed"] = request.form.get("bar_speed", "normal")
                if content["bar_speed"] not in {"slow", "normal", "fast"}:
                    raise ValueError("Choose a valid scrolling speed.")
                if content["bar_enabled"] and not content["bar_messages"]:
                    raise ValueError("Enter at least one announcement before enabling the bar.")
                for field in ("desktop_video", "mobile_video", "second_desktop_video", "second_mobile_video", "poster"):
                    if request.form.get(f"remove_{field}") == "1":
                        content[field] = ""
                    upload = request.files.get(field)
                    if upload and upload.filename:
                        key = (save_product_video(upload, None, 0, storage_prefix="storefront")["storage_key"]
                               if field.endswith("video") else save_image(upload))
                        created.append(key)
                        content[field] = key
                for index, banner in enumerate(content["banners"]):
                    prefix = f"banner_{index}_"
                    banner.update(enabled=request.form.get(prefix + "enabled") == "1",
                                  title=text(prefix + "title", 100), alt=text(prefix + "alt", 200),
                                  link=local_link(request.form.get(prefix + "link", "/shop")))
                    if request.form.get(prefix + "remove") == "1":
                        banner["image"] = ""
                    upload = request.files.get(prefix + "image")
                    if upload and upload.filename:
                        banner["image"] = save_image(upload)
                        created.append(banner["image"])
                    if banner["enabled"] and (not banner["image"] or not banner["alt"]):
                        raise ValueError(f"Banner {index + 1} needs an image and alternative text before enabling it.")
                row = db.session.get(StorefrontContent, 1)
                if row is None:
                    row = StorefrontContent(id=1)
                    db.session.add(row)
                row.content = content
                db.session.add(AuditLog(actor_user_id=current_user.id, action="storefront.updated", entity_type="storefront", entity_id="1"))
                db.session.commit()
                flash("Storefront saved. View the store to check your changes.", "success")
                return redirect(url_for("admin.storefront"))
            except Exception as exc:
                db.session.rollback()
                for key in created:
                    (Path(current_app.config["UPLOAD_DIR"]) / key).unlink(missing_ok=True)
                if not isinstance(exc, ValueError):
                    raise
                error = str(exc)
                content = get_content()
        return render_template("admin/storefront.html", content=content, error=error), 400 if error else 200
