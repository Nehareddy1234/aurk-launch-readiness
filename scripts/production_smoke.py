"""Read-only public website smoke checks. No sign-ins, uploads, or order changes."""
import argparse
import json
from pathlib import Path
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = set()
        self.products = set()
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in {"img", "script", "source"} and a.get("src"):
            self.assets.add(a["src"])
        if tag == "link" and a.get("rel") == "stylesheet":
            self.assets.add(a.get("href", ""))
        if tag == "a" and a.get("href", "").startswith("/product/"):
            self.products.add(a["href"])

def check(url, method="GET", headers=None):
    request = Request(url, method=method, headers={"User-Agent": "AURK-Production-Smoke/1.0", **(headers or {})})
    try:
        try:
            response = urlopen(request, timeout=20)
        except HTTPError as error:
            response = error
        with response:
            selected = {key: response.headers.get(key) for key in (
                "Content-Type", "Content-Length", "Cache-Control", "Content-Range",
                "Strict-Transport-Security", "X-Frame-Options", "X-Content-Type-Options",
                "Content-Security-Policy", "X-Robots-Tag") if response.headers.get(key)}
            body = response.read(1_000_000).decode("utf-8", errors="replace") if method == "GET" else ""
            cookies = response.headers.get_all("Set-Cookie", [])
            return {"url": url, "status": response.status, "final_url": response.url,
                    "headers": selected, "session_cookie_flags": [
                        {"secure": "; secure" in cookie.lower(), "httponly": "; httponly" in cookie.lower(),
                         "samesite": "samesite=lax" in cookie.lower()} for cookie in cookies],
                    "debug_traceback": "Traceback (most recent call last)" in body}, body
    except (URLError, TimeoutError, OSError) as error:
        return {"url": url, "error": str(error)}, ""

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", default="instance/production-live-results.json")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    if urlsplit(base).scheme != "https" or not urlsplit(base).hostname:
        parser.error("Use an HTTPS website URL.")
    pages = ["/", "/shop", "/auth/login", "/auth/register", "/cart", "/checkout", "/admin/", "/admin/products", "/admin/login", "/api/health", "/production-check-missing-page"]
    results = []
    links = Links()
    for path in pages:
        item, body = check(base + path)
        expected = 404 if path == "/production-check-missing-page" else 200
        item["passed"] = item.get("status") == expected and not item.get("debug_traceback")
        if path in {"/admin/", "/admin/products"}:
            item["passed"] = item["passed"] and urlsplit(item.get("final_url", "")).path == "/admin/login"
        if path == "/api/health":
            item["passed"] = item["passed"] and body.strip() == '{"status":"ok"}'
        results.append(item)
        if path in {"/", "/shop", "/admin/login"}:
            links.feed(body)
        if path == "/":
            item["old_homepage_guide_present"] = "SHOP AT YOUR PACE" in body
        print(path, item.get("status", item.get("error")))
    for path in sorted(links.products)[:1]:
        item, _ = check(urljoin(base, path))
        item["passed"] = item.get("status") == 200
        results.append(item)
        print(path, item.get("status", item.get("error")))
    for path in sorted(links.assets):
        url = urljoin(base, path)
        if urlsplit(url).netloc != urlsplit(base).netloc:
            continue
        item, _ = check(url, "HEAD")
        item["passed"] = item.get("status") == 200
        results.append(item)
        print(path, item.get("status", item.get("error")))
    videos = [path for path in links.assets if ".mp4" in path]
    if videos:
        item, _ = check(urljoin(base, sorted(videos)[0]), "GET", {"Range": "bytes=0-1023"})
        item["passed"] = item.get("status") == 206 and item.get("headers", {}).get("Content-Range", "").startswith("bytes 0-1023/")
        results.append(item)
        print("video-range", item.get("status", item.get("error")))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("Saved", output)
    failed = sum(not item["passed"] for item in results)
    print(f"{len(results) - failed}/{len(results)} checks passed.")
    raise SystemExit(1 if failed else 0)

if __name__ == "__main__":
    main()
