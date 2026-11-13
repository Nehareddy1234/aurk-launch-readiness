import io
import pytest
from PIL import Image
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import User, Role, Permission, Category, Product, ProductVariant, Size, Color, Order, OrderItem, CustomerPhoto

PASSWORD="StrongPassword123!"

def picture():
    file=io.BytesIO()
    image=Image.new("RGB",(40,50),"red")
    exif=Image.Exif()
    exif[270]="Private metadata"
    image.save(file,format="JPEG",exif=exif)
    file.seek(0)
    return file

@pytest.fixture
def community(client,tmp_path):
    client.application.config['UPLOAD_DIR']=str(tmp_path)
    client.application.config['MAX_CONTENT_LENGTH']=100*1024*1024
    with client.application.app_context():
        hashed=generate_password_hash(PASSWORD)
        buyer=User(email="photo@example.com",first_name="Photo",last_name="Buyer",password_hash=hashed)
        other=User(email="other@example.com",first_name="Other",last_name="Buyer",password_hash=hashed)
        admin=User(email="admin@example.com",first_name="Admin",last_name="Owner",password_hash=hashed,
            roles=[Role(name="Admin",permissions=[Permission(name="reviews.manage")])])
        product=Product(name="Photo Tee",slug="photo-tee",base_price=999,category=Category(name="Tees",slug="tees"))
        variant=ProductVariant(product=product,size=Size(name="M"),color=Color(name="Red"),sku="PHOTO-M")
        db.session.add_all([buyer,other,admin,variant]);db.session.flush()
        ids=[]
        for i,(user,status) in enumerate([(buyer,"Delivered"),(buyer,"Pending"),(other,"Delivered")]):
            order=Order(user_id=user.id,order_number=f"PHOTO-{i}",status=status,subtotal=999,total=999,
                shipping_name="Buyer",shipping_phone="9876543210",shipping_line1="Private Address",shipping_city="Mumbai",
                shipping_state="Maharashtra",shipping_postal_code="400001",shipping_country="India")
            item=OrderItem(order=order,variant_id=variant.id,product_name_snapshot="Photo Tee",sku_snapshot="PHOTO-M",
                size_snapshot="M",color_snapshot="Red",unit_price=999,quantity=1,line_total=999)
            db.session.add(item);db.session.flush();ids.append(item.id)
        db.session.commit()
        return ids,product.id,tmp_path

def sign_in(client,email="photo@example.com",admin=False):
    client.post("/auth/logout")
    result=client.post("/admin/login" if admin else "/auth/login",data={"email":email,"password":PASSWORD})
    assert result.status_code==302

def upload(client,item,**extra):
    return client.post("/worn-by-you/upload",data={"order_item_id":str(item),"publish_consent":"1",
        "caption":"My fit", "photo":(picture(),"photo.jpg"),**extra},content_type="multipart/form-data")

def test_gallery_public_upload_requires_signin(client,community):
    assert client.get("/worn-by-you").status_code==200
    assert b"Sign in to upload" in client.get("/worn-by-you").data
    assert upload(client,community[0][0]).status_code==302
    with client.application.app_context(): assert CustomerPhoto.query.count()==0

@pytest.mark.parametrize("which",[1,2,999])
def test_requires_own_delivered_item(client,community,which):
    sign_in(client)
    item=community[0][which] if which<3 else 99999
    assert upload(client,item).status_code==403
    with client.application.app_context(): assert CustomerPhoto.query.count()==0

def test_pending_private_approved_public_and_withdrawal(client,community):
    ids,product_id,root=community
    sign_in(client)
    assert upload(client,ids[0],product_id="999999").status_code==302
    with client.application.app_context():
        row=CustomerPhoto.query.one();pid=row.id
        assert row.status=="pending" and row.product_id==product_id
        with Image.open(root/row.storage_key) as photo:
            assert photo.format=="JPEG" and not photo.getexif()
    assert client.get(f"/worn-by-you/photos/{pid}").status_code==200
    client.post("/auth/logout")
    assert client.get(f"/worn-by-you/photos/{pid}").status_code==404
    assert b"My fit" not in client.get("/worn-by-you").data
    sign_in(client,"other@example.com")
    assert client.get(f"/worn-by-you/photos/{pid}").status_code==404
    assert client.post(f"/worn-by-you/{pid}/withdraw").status_code==404
    assert client.post(f"/admin/worn-by-you/{pid}",data={"action":"approve"}).status_code==403
    sign_in(client,"admin@example.com",True)
    assert client.get("/admin/worn-by-you").status_code==200
    assert client.get(f"/worn-by-you/photos/{pid}").status_code==200
    assert client.post(f"/admin/worn-by-you/{pid}",data={"action":"approve"}).status_code==302
    client.post("/auth/logout")
    page=client.get("/worn-by-you")
    assert b"My fit" in page.data and b"VERIFIED PURCHASE" in page.data
    assert b"Private Address" not in page.data and b"photo@example.com" not in page.data
    photo=client.get(f"/worn-by-you/photos/{pid}")
    assert photo.status_code==200 and photo.mimetype=="image/jpeg"
    assert photo.headers["Cache-Control"]=="no-store, private"
    sign_in(client)
    assert client.post(f"/worn-by-you/{pid}/withdraw").status_code==302
    sign_in(client,"admin@example.com",True)
    assert client.post(f"/admin/worn-by-you/{pid}",data={"action":"approve"}).status_code==409
    client.post("/auth/logout")
    assert client.get(f"/worn-by-you/photos/{pid}").status_code==404
    assert b"My fit" not in client.get("/worn-by-you").data

def test_validation_and_csrf(client,community):
    sign_in(client)
    item=community[0][0]
    for extra in ({"publish_consent":""},{"caption":"x"*401},{"photo":(io.BytesIO(b"not an image"),"fake.jpg")},
                  {"photo":(io.BytesIO(b"x"*(8*1024*1024+1)),"large.jpg")}):
        assert upload(client,item,**extra).status_code==302
    with client.application.app_context(): assert CustomerPhoto.query.count()==0
    assert not list(community[2].rglob("*.jpg"))
    client.application.config["WTF_CSRF_ENABLED"]=True
    assert upload(client,item).status_code==400

def test_limit_and_rejected_photo_private(client,community):
    sign_in(client)
    item=community[0][0]
    for _ in range(6): assert upload(client,item).status_code==302
    with client.application.app_context():
        assert CustomerPhoto.query.count()==5
        row=CustomerPhoto.query.first();pid=row.id
    sign_in(client,"admin@example.com",True)
    assert client.post(f"/admin/worn-by-you/{pid}",data={"action":"reject"}).status_code==302
    assert client.get("/admin/worn-by-you?status=rejected").status_code==200
    client.post("/auth/logout")
    assert client.get(f"/worn-by-you/photos/{pid}").status_code==404
