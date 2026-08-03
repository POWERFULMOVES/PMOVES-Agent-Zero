import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEBUI_ROOT = PROJECT_ROOT / "webui"
PLUGINS_ROOT = PROJECT_ROOT / "plugins"
LEGACY_ICON_SPAN = re.compile(
    r"<span\b(?=[^>]*\b(?:material-symbols-outlined|material-icons-outlined)\b)",
    re.IGNORECASE,
)


def first_party_icon_sources() -> list[Path]:
    roots = [WEBUI_ROOT]
    roots.extend(
        path
        for path in sorted(PLUGINS_ROOT.iterdir())
        if path.is_dir() and path.name.startswith("_")
    )
    return [
        path
        for root in roots
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix in {".html", ".js"}
        and not {"vendor", "node_modules"}.intersection(path.relative_to(root).parts)
    ]


def iter_x_icons(source: str):
    cursor = 0
    while True:
        start = source.find("<x-icon", cursor)
        if start < 0:
            return

        quote = ""
        end = start + len("<x-icon")
        while end < len(source):
            char = source[end]
            if quote:
                if char == quote and source[end - 1] != "\\":
                    quote = ""
            elif char in {'"', "'"}:
                quote = char
            elif char == ">":
                break
            end += 1

        close = source.find("</x-icon>", end + 1)
        assert end < len(source) and close >= 0
        yield source[start : end + 1], source[end + 1 : close]
        cursor = close + len("</x-icon>")


def test_first_party_webui_uses_empty_named_x_icon_elements() -> None:
    legacy_offenders: list[str] = []
    malformed: list[str] = []
    icon_count = 0

    for path in first_party_icon_sources():
        source = path.read_text(encoding="utf-8")
        if LEGACY_ICON_SPAN.search(source):
            legacy_offenders.append(str(path.relative_to(PROJECT_ROOT)))

        for start_tag, content in iter_x_icons(source):
            icon_count += 1
            if (
                content.strip()
                or re.search(r"\sx-text\s*=", start_tag)
                or not re.search(r"(?:^|\s)(?::name|name)\s*=", start_tag)
            ):
                malformed.append(
                    f"{path.relative_to(PROJECT_ROOT)}: {start_tag[:160]}"
                )

    assert icon_count >= 500
    assert legacy_offenders == []
    assert malformed == []


def test_x_icon_is_font_backed_and_keeps_legacy_plugin_compatibility() -> None:
    icons_js = (WEBUI_ROOT / "js" / "icons.js").read_text(encoding="utf-8")
    icon_css = (WEBUI_ROOT / "vendor" / "google" / "google-icons.css").read_text(
        encoding="utf-8"
    )
    index_html = (WEBUI_ROOT / "index.html").read_text(encoding="utf-8")

    assert '<script type="module" src="/js/icons.js"></script>' in index_html
    assert 'customElements.define(' in icons_js
    assert 'return ["name"]' in icons_js
    assert 'this.classList.add("material-symbols-outlined")' in icons_js
    assert ".material-symbols-outlined" in icons_js
    assert ".material-icons-outlined" in icons_js
    assert "maskImage" not in icons_js
    assert "/vendor/icons/" not in icons_js

    assert "x-icon," in icon_css
    assert ".material-symbols-outlined," in icon_css
    assert ".material-icons-outlined" in icon_css
    assert "width: 1em !important" in icon_css
    assert "overflow: hidden !important" in icon_css
    assert (
        "document.fonts.load('24px \"Material Symbols Outlined\"')"
        in index_html
    )
    assert (
        'document.addEventListener("DOMContentLoaded", loadMaterialIcons, { once: true })'
        in index_html
    )
