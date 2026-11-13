"""Real Chromium journeys against an isolated loopback-only Flask server."""
from io import BytesIO
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit

import pytest
from PIL import Image
from werkzeug.serving import make_server

from app.extensions import db
from app.models import ProductImage, Order, CustomerEmail


def test_home_scroll_header(browser_store, chromium):
    from playwright.sync_api import expect
    page = chromium
    for width in (375, 1440):
        page.set_viewport_size({'width': width, 'height': 900})
        page.goto(browser_store['base'] + '/', wait_until='domcontentloaded')
        expect(page.locator('[data-home-intro]')).to_have_count(0)
        expect(page.locator('#aurk-header')).to_be_hidden()
        assert not page.locator('#main-content').evaluate('el => el.inert')
        page.evaluate('window.scrollTo(0, 300)')
        expect(page.locator('#aurk-header')).to_be_visible()
        page.evaluate('window.scrollTo(0, 0)')
        expect(page.locator('#aurk-header')).to_be_hidden()
    page.goto(browser_store['base'] + '/shop')
    expect(page.locator('[data-home-intro]')).to_have_count(0)
    expect(page.locator('#aurk-header')).to_be_visible()


def test_coming_soon_badge_design(browser_store, chromium):
    from playwright.sync_api import expect
    page = chromium
    for width in (375, 1440):
        page.set_viewport_size({'width': width, 'height': 900})
        page.emulate_media(reduced_motion='no-preference')
        page.goto(browser_store['base'] + '/product/browser-launch')
        badge = page.locator('.coming-soon-badge')
        expect(badge).to_have_text('COMING SOON')
        expect(badge).to_be_visible()
        assert badge.locator('.coming-soon-dot').evaluate('el => getComputedStyle(el).animationName') == 'coming-soon-pulse'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=f'qa_artifacts/coming-soon-{width}.png')
        page.emulate_media(reduced_motion='reduce')
        assert badge.locator('.coming-soon-dot').evaluate('el => getComputedStyle(el).animationName') == 'none'
    page.goto(browser_store['base'] + '/shop')
    expect(page.locator('.coming-soon-badge')).to_have_count(1)


def test_product_photos_advance_automatically(browser_store, chromium):
    from playwright.sync_api import expect
    page = chromium
    page.emulate_media(reduced_motion='no-preference')
    page.clock.install()
    page.goto(browser_store['base'] + '/product/browser-tee')
    count = page.locator('[data-photo-count]')
    expect(count).to_have_text('Photo 1 of 2')
    page.mouse.move(1, 1)
    page.clock.run_for(5200)
    expect(count).to_have_text('Photo 2 of 2')
    page.locator('.shopping-main-image').hover()
    page.clock.run_for(5200)
    expect(count).to_have_text('Photo 2 of 2')
    page.mouse.move(1, 1)
    page.clock.run_for(5200)
    expect(count).to_have_text('Photo 1 of 2')


def test_size_chart_opens_only_on_click(browser_store, chromium):
    from playwright.sync_api import expect
    page = chromium
    base = browser_store['base']
    for width in (375, 1440):
        page.set_viewport_size({'width': width, 'height': 900})
        page.goto(base + '/product/browser-tee')
        dialog = page.get_by_role('dialog', name='AURK size guide')
        expect(dialog).not_to_be_visible()
        size = page.locator('[data-size-select]')
        size.select_option(str(browser_store['variant'].size_id))
        selected = size.input_value()
        button = page.get_by_role('button', name='Size chart', exact=True)
        button.click()
        expect(dialog).to_be_visible()
        expect(dialog.get_by_role('row')).to_have_count(9)
        expect(dialog.get_by_role('row', name='XXS 30–32 38 / 19 24.00 19.00 7.50', exact=True)).to_be_visible()
        expect(dialog.get_by_role('row', name='3XL 44–46 52 / 26 29.25 24.25 9.25', exact=True)).to_be_visible()
        expect(dialog).to_contain_text('At a range boundary, choose the smaller size: 36 inches = S')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert dialog.evaluate('el => el.getBoundingClientRect().width <= innerWidth')
        Path('qa_artifacts').mkdir(exist_ok=True)
        page.screenshot(path=f'qa_artifacts/size-chart-{width}.png')
        page.keyboard.press('Escape')
        expect(dialog).not_to_be_visible()
        expect(button).to_be_focused()
        assert size.input_value() == selected
        button.click()
        dialog.get_by_role('button', name='Close size chart').click()
        expect(dialog).not_to_be_visible()
    assert page.request.get(base + '/static/images/guides/aurk-size-guide-inches.png').status == 200
    page.goto(base + '/shop')
    page.locator('.card-options').first.locator('summary').click()
    page.get_by_role('button', name='Size chart', exact=True).first.click()
    expect(page.get_by_role('dialog', name='AURK size guide')).to_be_visible()


def test_admin_storefront_campaign(browser_store, chromium):
    from playwright.sync_api import expect
    page = chromium
    page.emulate_media(reduced_motion="no-preference")
    base = browser_store["base"]
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(base + "/admin/login")
    page.locator('[name="email"]').fill(browser_store["owner"].email)
    page.locator('[name="password"]').fill("QaPassword123!")
    page.locator('form button[type="submit"]').click()
    page.goto(base + "/admin/storefront")
    page.locator('[name="bar_enabled"]').check()
    page.locator('[name="bar_messages"]').fill("QA weekend sale\nNew collection")
    page.locator('[name="cover_title"]').fill("QA BIG DROP")
    picture = BytesIO()
    Image.new("RGB", (1200, 400), "orange").save(picture, "PNG")
    page.locator('[name="banner_0_image"]').set_input_files({"name": "banner.png", "mimeType": "image/png", "buffer": picture.getvalue()})
    page.locator('[name="banner_0_enabled"]').check()
    page.locator('[name="banner_0_alt"]').fill("QA orange banner")
    page.get_by_role("button", name="Save storefront").click()
    expect(page.get_by_text("Storefront saved.", exact=False)).to_be_visible()
    for width in (375, 1440):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(base + "/")
        expect(page.get_by_role("heading", name="QA BIG DROP")).to_be_visible()
        expect(page.get_by_alt_text("QA orange banner")).to_be_visible()
        assert page.get_by_alt_text("QA orange banner").evaluate("img => img.naturalWidth") > 0
        expect(page.locator(".promotion-bar").get_by_role("button")).to_have_count(0)
        page.locator(".promotion-bar").hover()
        assert page.locator(".promotion-track").evaluate("el => getComputedStyle(el).animationPlayState") == "paused"
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        Path("qa_artifacts").mkdir(exist_ok=True)
        page.screenshot(path=f"qa_artifacts/storefront-{width}.png", full_page=True)
    page.emulate_media(reduced_motion="reduce")
    assert page.locator('.promotion-track').evaluate("el => getComputedStyle(el).animationName") == "none"
    assert not errors, errors


@pytest.fixture
def browser_store(app, qa_factory, mocked_smtp):
    buyer = qa_factory.customer()
    owner = qa_factory.admin()
    product = qa_factory.product(name="Browser Tee", slug="browser-tee", is_featured=True)
    launch = qa_factory.product(name="Browser Launch", slug="browser-launch", product_status="coming_soon", hide_price=True)
    variant = qa_factory.variant(product=product, stock=3)
    qa_factory.variant(product=product, stock=0)
    with app.app_context():
        for n, color in enumerate(("red", "blue")):
            image = BytesIO(); Image.new("RGB", (240, 300), color).save(image, format="PNG")
            key = f"qa-browser-{n}.png"
            (Path(app.config["UPLOAD_DIR"]) / key).write_bytes(image.getvalue())
            db.session.add(ProductImage(product_id=product.id, storage_key=key, mime_type="image/png",
                file_size=len(image.getvalue()), width=240, height=300, sort_order=n, is_primary=n==0))
        db.session.commit()
    app.config.update(WTF_CSRF_ENABLED=True, CUSTOMER_EMAILS_ENABLED=True, PUBLIC_BASE_URL="https://aurk.test")
    server = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield dict(base=f"http://127.0.0.1:{server.server_port}", buyer=buyer, owner=owner,
               product=product, launch=launch, variant=variant, app=app)
    server.shutdown(); thread.join(timeout=5)


def test_banner_carousel_autoplay_hover_and_navigation(browser_store, chromium):
    from playwright.sync_api import expect
    from werkzeug.datastructures import FileStorage
    from app.models import StorefrontContent
    from app.services.storefront import get_content, save_image
    page = chromium
    with browser_store["app"].app_context():
        content = get_content()
        for index, color in enumerate(("orange", "blue", "green")):
            picture = BytesIO()
            Image.new("RGB", (1920, 640), color).save(picture, "PNG")
            picture.seek(0)
            key = save_image(FileStorage(stream=picture, filename="banner.png"))
            content["banners"][index].update(enabled=True, image=key, alt=f"QA slide {index + 1}")
        db.session.add(StorefrontContent(id=1, content=content))
        db.session.commit()
    page.emulate_media(reduced_motion="no-preference")
    page.clock.install()
    page.goto(browser_store["base"] + "/")
    carousel = page.locator('[data-banner-carousel]')
    expect(carousel).to_have_attribute('data-active-banner', '0')
    page.clock.run_for(5800)
    expect(carousel).to_have_attribute('data-active-banner', '1')
    expect(page.locator('.banner-viewport')).to_have_js_property('scrollLeft', page.locator('.banner-viewport').evaluate('el => el.clientWidth'))
    carousel.hover()
    page.clock.run_for(6500)
    expect(carousel).to_have_attribute('data-active-banner', '1')
    page.mouse.move(1, 1)
    page.clock.run_for(5800)
    expect(carousel).to_have_attribute('data-active-banner', '2')
    expect(page.locator('.banner-viewport')).to_have_js_property('scrollLeft', page.locator('.banner-viewport').evaluate('el => 2 * el.clientWidth'))
    expect(carousel.get_by_role('button')).to_have_count(0)
    for width in (375, 1440):
        page.set_viewport_size({"width": width, "height": 900})
        page.clock.run_for(300)
        assert carousel.evaluate('el => Math.abs(el.getBoundingClientRect().width - innerWidth) < 2')
        assert page.locator('.banner-viewport').evaluate('el => Math.abs(el.getBoundingClientRect().width - innerWidth) < 2')
        geometry = page.evaluate('''() => {
            const cover = document.querySelector('.aurk-campaign').getBoundingClientRect();
            const banner = document.querySelector('.marketing-banners').getBoundingClientRect();
            const video = document.querySelector('.aurk-campaign video').getBoundingClientRect();
            return {coverHeight:cover.height, viewportHeight:innerHeight, gap:banner.top-cover.bottom,
                    videoHeight:video.height, videoWidth:video.width, coverWidth:cover.width};
        }''')
        assert geometry['coverHeight'] >= geometry['viewportHeight'] - 1
        assert geometry['gap'] >= 24
        assert abs(geometry['videoHeight'] - geometry['coverHeight']) < 2
        assert abs(geometry['videoWidth'] - geometry['coverWidth']) < 2
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.emulate_media(reduced_motion="reduce")
    page.clock.run_for(1000)
    stopped_index = int(carousel.get_attribute('data-active-banner'))
    page.clock.run_for(6000)
    expect(carousel).to_have_attribute('data-active-banner', str(stopped_index))
    page.locator('.banner-viewport').focus()
    page.keyboard.press('ArrowLeft')
    page.clock.run_for(300)
    expect(carousel).to_have_attribute('data-active-banner', str((stopped_index - 1) % 3))


@pytest.fixture
def chromium(browser_store):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as runner:
        browser = runner.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width":1440,"height":1000}, reduced_motion="reduce")
        # Never let the browser visit production, third-party fonts, SMTP APIs, etc.
        context.route("**/*", lambda route: route.continue_() if urlsplit(route.request.url).hostname == "127.0.0.1" else route.abort())
        page = context.new_page()
        page.set_default_timeout(8000)
        yield page
        context.close(); browser.close()


def test_cover_video_advances_on_actual_playback_end(browser_store, chromium):
    from playwright.sync_api import expect
    from werkzeug.datastructures import FileStorage
    from app.models import StorefrontContent
    from app.services.storefront import get_content
    from app.services.product_video import save_product_video
    app = browser_store['app']
    with app.app_context():
        content = get_content()
        with (Path(app.static_folder) / 'videos/store-cover.mp4').open('rb') as source:
            key = save_product_video(FileStorage(stream=source, filename='second.mp4'), None, 0, storage_prefix='storefront')['storage_key']
        content['second_desktop_video'] = key
        db.session.add(StorefrontContent(id=1, content=content))
        db.session.commit()
    page = chromium
    page.emulate_media(reduced_motion='no-preference')
    page.goto(browser_store['base'] + '/', wait_until='domcontentloaded')
    track = page.locator('[data-cover-playlist]')
    expect(track.locator('video')).to_have_count(2)
    expect(page.locator('.storefront-benefits')).to_have_count(0)
    page.wait_for_function("() => document.querySelectorAll('[data-cover-playlist] video')[0].readyState >= 2")
    page.locator('[data-cover-playlist] video').nth(0).evaluate('(video) => { video.currentTime = video.duration - 0.25; return video.play(); }')
    expect(track).to_have_attribute('data-active-video', '1')
    page.wait_for_function("() => !document.querySelectorAll('[data-cover-playlist] video')[1].paused")
    assert track.locator('video').nth(0).evaluate('video => video.paused')
    track.locator('video').nth(1).evaluate('(video) => { video.currentTime = video.duration - 0.25; }')
    expect(track).to_have_attribute('data-active-video', '0')
    page.wait_for_function("() => !document.querySelectorAll('[data-cover-playlist] video')[0].paused")
    assert track.locator('video').nth(1).evaluate('video => video.paused')


def browser_login(page, base, user, admin=False):
    page.goto(base + ("/admin/login" if admin else "/auth/login"))
    page.locator('[name="email"]').fill(user.email)
    page.locator('[name="password"]').fill("QaPassword123!")
    page.locator('form button').first.click()
    page.wait_for_url("**/admin/dashboard" if admin else "**/account/")


def test_browser_complete_cod_journey(browser_store, chromium):
    from playwright.sync_api import expect
    page=chromium; store=browser_store; base=store["base"]
    errors=[]; failures=[]
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: failures.append([response.status,response.url]) if response.status>=400 else None)
    page.goto(base+"/shop")
    page.goto(base+"/product/browser-tee")
    page.locator('[data-size-select]').select_option(str(store["variant"].size_id))
    page.get_by_role("button", name="Add to cart", exact=True).click()
    page.wait_for_url("**/cart")
    page.goto(base+"/checkout")
    expect(page.locator('h1')).to_contain_text("Sign in")
    page.locator('[name="email"]').fill(store["buyer"].email)
    page.locator('[name="password"]').fill("QaPassword123!")
    page.locator('form button').first.click()
    page.wait_for_url("**/checkout")
    for name,value in {"recipient_name":"QA Buyer","phone":"9876543210","line1":"1 QA Road","city":"Mumbai","state":"Maharashtra","postal_code":"400001"}.items():
        page.locator(f'[name="{name}"]').fill(value)
    page.get_by_role("button",name="Place COD order").click()
    page.wait_for_url("**/checkout/success/**")
    with store["app"].app_context():
        order=Order.query.one(); number=order.order_number
        assert order.status=="Pending"
        assert CustomerEmail.query.filter_by(kind="order_received").count()==1
    page.goto(base+"/account/orders")
    expect(page.locator("main")).to_contain_text(number)
    assert not errors,errors
    assert not failures,failures


@pytest.mark.parametrize("width", [375,1440])
def test_browser_gallery_notify_layout_and_console(browser_store,chromium,width):
    from playwright.sync_api import expect
    page=chromium; base=browser_store["base"]
    page.set_viewport_size({"width":width,"height":900})
    errors=[]; page.on("pageerror", lambda error: errors.append(str(error)))
    measurements=[]
    for path in ("/", "/shop", "/product/browser-tee", "/cart", "/auth/login", "/worn-by-you"):
        page.goto(base+path)
        measurements.append({"path":path,"width":width,**page.evaluate('({viewport:innerWidth, document:document.documentElement.scrollWidth})')})
    page.goto(base+"/product/browser-tee")
    # The gallery replaces the original image with an animated track.
    original=page.locator("#fullProductImage").get_attribute("href")
    buttons=page.locator('[data-photo-source]')
    assert buttons.count()==2
    buttons.nth(1).click()
    expect(page.locator("#fullProductImage")).not_to_have_attribute("href",original)
    page.goto(base+"/product/browser-launch")
    page.get_by_role("link",name="Notify me").click()
    expect(page).to_have_url(__import__('re').compile(r"/auth/login\?next="))
    page.locator('[name="email"]').fill(browser_store["buyer"].email)
    page.locator('[name="password"]').fill("QaPassword123!")
    page.locator('form button').first.click()
    page.wait_for_url("**/product/browser-launch")
    page.get_by_role("button",name="Notify me").click()
    expect(page.get_by_role("button",name="You're on the list")).to_be_disabled()
    with browser_store["app"].app_context():
        assert CustomerEmail.query.filter_by(kind="notify_interest").count()==1
    artifact=Path("qa_artifacts");artifact.mkdir(exist_ok=True)
    (artifact/f"layout-{width}.json").write_text(json.dumps(measurements,indent=2),encoding="utf-8")
    page.screenshot(path=str(artifact/f"notify-{width}.png"),full_page=True)
    assert not errors,errors
    assert all(row["document"]<=row["viewport"]+1 for row in measurements),measurements


def test_QA_UI_001_admin_upload_preview_not_blocked_by_csp(browser_store,chromium):
    page=chromium;store=browser_store
    browser_login(page,store["base"],store["owner"],admin=True)
    page.goto(store["base"]+"/admin/products/create")
    image=BytesIO();Image.new("RGB",(24,30),"white").save(image,format="PNG")
    page.locator('[data-image-upload]').set_input_files({"name":"qa.png","mimeType":"image/png","buffer":image.getvalue()})
    page.wait_for_function('() => document.querySelector("[data-upload-list] img") !== null')
    page.wait_for_function('() => document.querySelector("[data-upload-list] img").complete')
    assert page.locator('[data-upload-list] img').evaluate('(img)=>img.complete && img.naturalWidth>0'), "QA-UI-001: CSP blocks blob: upload preview"


def test_QA_A11Y_001_key_pages_have_no_serious_axe_violations(browser_store,chromium):
    page=chromium;store=browser_store
    axe=Path("qa_artifacts/axe.min.js")
    if not axe.exists():
        pytest.skip("axe-core asset unavailable; run scripts/run_qa.py browser-setup")
    results=[]
    public=("/", "/shop", "/product/browser-tee", "/cart", "/auth/login", "/admin/login")
    for path in public:
        page.goto(store["base"]+path)
        page.evaluate(axe.read_text(encoding="utf-8"))
        result=page.evaluate('async () => await axe.run(document, {runOnly:{type:"tag",values:["wcag2a","wcag2aa","wcag21aa"]}})')
        results.append({"path":path,"violations":result["violations"]})
    browser_login(page,store["base"],store["buyer"])
    page.goto(store["base"]+"/product/browser-tee")
    page.locator('[data-size-select]').select_option(str(store["variant"].size_id))
    page.get_by_role("button",name="Add to cart",exact=True).click()
    for path in ("/account/","/checkout"):
        page.goto(store["base"]+path)
        page.evaluate(axe.read_text(encoding="utf-8"))
        result=page.evaluate('async () => await axe.run(document, {runOnly:{type:"tag",values:["wcag2a","wcag2aa","wcag21aa"]}})')
        results.append({"path":path,"violations":result["violations"]})
    Path("qa_artifacts/accessibility.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
    serious=[(r["path"],v["id"],v["impact"]) for r in results for v in r["violations"] if v["impact"] in {"serious","critical"}]
    assert not serious,serious


@pytest.mark.parametrize('width',[320,390,768,1440])
def test_launch_page_reflow_navigation_and_metadata(browser_store,chromium,width):
    page=chromium;base=browser_store['base']
    page.set_viewport_size({'width':width,'height':900})
    for path in ('/','/shop','/product/browser-tee','/contact','/shipping','/returns','/refund-policy','/privacy','/terms','/auth/register','/missing-launch-page'):
        page.goto(base+path)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'),path
        assert page.locator('h1').count()>=1,path
        assert page.locator('title').text_content().strip(),path
        assert page.locator('meta[name="description"]').get_attribute('content'),path
        assert page.locator('img:not([alt])').count()==0,path
        assert page.locator('a[href="#"], a:not([href])').count()==0,path
    page.goto(base+'/shop')
    links=page.locator('footer nav a').evaluate_all('(links)=>links.map(a=>a.getAttribute("href"))')
    for path in links:
        response=page.request.get(base+path)
        assert response.status < 400,(path,response.status)
    if width<=768:
        page.locator('.site-menu-toggle').click()
        assert page.locator('#store-navigation').is_visible()
        page.locator('#store-navigation').get_by_role('link',name='Contact',exact=True).click()
        page.wait_for_url('**/contact')
    page.goto(base+'/')
    cta=page.locator('.aurk-campaign-copy a.button')
    box=cta.bounding_box()
    assert box and box['y']>=0 and box['y']+box['height']<=900
    assert page.get_by_role('button',name='Play background video',exact=True).is_visible()
    assert page.locator('[data-cover-playlist] video').first.evaluate('(v)=>v.paused')
    page.emulate_media(reduced_motion='no-preference')
    page.get_by_role('button',name='Pause background video',exact=True).click()
    assert page.locator('[data-cover-playlist] video').first.evaluate('(v)=>v.paused')
    assert page.locator('[data-cover-playlist] video').first.evaluate('(v)=>!v.controls')
    page.screenshot(path=f'qa_artifacts/launch-home-{width}.png',full_page=False,animations='disabled')


def test_merchant_variant_link_preserves_purchase_selection(browser_store,chromium):
    from playwright.sync_api import expect
    variant=browser_store['variant'];page=chromium
    page.goto(browser_store['base']+f'/product/browser-tee?variant={variant.id}')
    expect(page.locator('[name="variant_id"]')).to_have_value(str(variant.id))
    expect(page.locator('[data-size-select]')).to_have_value(str(variant.size_id))
    expect(page.locator('[data-colour-select]')).to_have_value(str(variant.color_id))
    page.get_by_role('button',name='Add to cart',exact=True).click()
    page.wait_for_url('**/cart')
    expect(page.get_by_text('Browser Tee',exact=True)).to_be_visible()
