import re
from html.parser import HTMLParser
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEBUI_ROOT = PROJECT_ROOT / "webui"
REMOTE_URL = re.compile(r"^(?:https?:)?//", re.IGNORECASE)
REMOTE_CSS_ASSET = re.compile(
    r"(?:@import\s+(?:url\()?|url\()\s*['\"]?(?:https?:)?//",
    re.IGNORECASE,
)


class PassiveAssetParser(HTMLParser):
    passive_link_relations = {
        "icon",
        "manifest",
        "modulepreload",
        "prefetch",
        "preload",
        "stylesheet",
    }

    def __init__(self) -> None:
        super().__init__()
        self.remote_assets: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = dict(attrs)
        candidates: list[str] = []

        if tag in {"audio", "embed", "iframe", "img", "script", "source", "video"}:
            candidates.extend(filter(None, (values.get("src"), values.get("poster"))))
        elif tag == "link":
            relations = set((values.get("rel") or "").lower().split())
            if relations & self.passive_link_relations:
                candidates.extend(filter(None, (values.get("href"),)))

        self.remote_assets.extend(value for value in candidates if REMOTE_URL.match(value))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_core_stylesheets_do_not_load_remote_assets() -> None:
    offenders = []
    for path in WEBUI_ROOT.rglob("*.css"):
        if "vendor" in path.parts:
            continue
        if REMOTE_CSS_ASSET.search(read(path)):
            offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert offenders == []


def test_webui_markup_does_not_passively_load_remote_assets() -> None:
    offenders: dict[str, list[str]] = {}
    for path in WEBUI_ROOT.rglob("*.html"):
        parser = PassiveAssetParser()
        parser.feed(read(path))
        if parser.remote_assets:
            offenders[str(path.relative_to(PROJECT_ROOT))] = parser.remote_assets

    assert offenders == {}


def test_main_and_login_pages_load_the_shared_local_font_stylesheet() -> None:
    index_html = read(WEBUI_ROOT / "index.html")
    login_html = read(WEBUI_ROOT / "login.html")

    assert 'href="/vendor/fonts/fonts.css"' in index_html
    assert 'href="/vendor/fonts/fonts.css"' in login_html
    assert "fonts.googleapis.com" not in read(WEBUI_ROOT / "index.css")
    assert "fonts.googleapis.com" not in read(WEBUI_ROOT / "login.css")


def test_login_uses_full_svg_logo() -> None:
    login_html = read(WEBUI_ROOT / "login.html")

    assert 'src="/public/dark.svg"' in login_html
    assert (WEBUI_ROOT / "public" / "dark.svg").is_file()
    assert 'src="/public/splash.jpg"' not in login_html


def test_vendored_variable_font_bundle_is_complete() -> None:
    fonts_root = WEBUI_ROOT / "vendor" / "fonts"
    font_css = read(fonts_root / "fonts.css")
    expected_fonts = {
        "rubik-variable.ttf": (
            'font-family: "Rubik"',
            "font-style: normal",
            "font-weight: 300 900",
        ),
        "rubik-italic-variable.ttf": (
            'font-family: "Rubik"',
            "font-style: italic",
            "font-weight: 300 900",
        ),
        "roboto-mono-variable.ttf": (
            'font-family: "Roboto Mono"',
            "font-style: normal",
            "font-weight: 100 700",
        ),
        "roboto-mono-italic-variable.ttf": (
            'font-family: "Roboto Mono"',
            "font-style: italic",
            "font-weight: 100 700",
        ),
    }

    for filename, declarations in expected_fonts.items():
        font_path = fonts_root / filename
        font_face = next(
            block
            for block in re.findall(r"@font-face\s*\{([^}]+)\}", font_css)
            if f'url("./{filename}")' in block
        )
        assert font_path.read_bytes()[:4] == b"\x00\x01\x00\x00"
        assert all(declaration in font_face for declaration in declarations)

    assert REMOTE_CSS_ASSET.search(font_css) is None
    assert (fonts_root / "rubik-OFL.txt").is_file()
    assert (fonts_root / "roboto-mono-OFL.txt").is_file()


def test_material_icon_font_is_preloaded_and_layout_stable() -> None:
    icon_root = WEBUI_ROOT / "vendor" / "google"
    icon_css = read(icon_root / "google-icons.css")
    index_html = read(WEBUI_ROOT / "index.html")
    splash_html = read(WEBUI_ROOT / "splash.html")

    assert (icon_root / "google-icons.woff2").read_bytes()[:4] == b"wOF2"
    assert "url(./google-icons.woff2) format('woff2')" in icon_css
    assert "font-display: block" in icon_css
    assert "width: 1em !important" in icon_css
    assert "min-width: 1em !important" in icon_css
    assert "max-width: 1em !important" in icon_css
    assert "height: 1em !important" in icon_css
    assert "overflow: hidden !important" in icon_css
    assert "html:not(.material-icons-ready)" in icon_css
    assert "x-icon," in icon_css
    assert ".material-symbols-outlined," in icon_css
    assert ".material-icons-outlined" in icon_css
    preload = (
        '<link rel="preload" href="/vendor/google/google-icons.woff2" '
        'as="font" type="font/woff2" crossorigin>'
    )
    assert preload in index_html
    assert preload not in splash_html
