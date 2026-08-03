const ICON_TAG = "x-icon";
const ICON_NAME_PATTERN = /^[a-z0-9][a-z0-9_]*$/;

export const ICON_SELECTOR = `${ICON_TAG}, .material-symbols-outlined, .material-icons-outlined`;

export function normalizeIconName(value) {
  const name = String(value ?? "").trim();
  return ICON_NAME_PATTERN.test(name) ? name : "";
}

export function getIconName(element) {
  if (!element) return "";
  if (element.localName === ICON_TAG) {
    return normalizeIconName(element.getAttribute("name"));
  }
  return normalizeIconName(element.textContent);
}

export function setIconName(element, value) {
  if (!element) return;
  const name = normalizeIconName(value);
  if (element.localName === ICON_TAG) {
    if (name) element.setAttribute("name", name);
    else element.removeAttribute("name");
    return;
  }
  element.textContent = name;
}

if (!customElements.get(ICON_TAG)) {
  customElements.define(
    ICON_TAG,
    class extends HTMLElement {
      static get observedAttributes() {
        return ["name"];
      }

      get name() {
        return normalizeIconName(this.getAttribute("name"));
      }

      set name(value) {
        setIconName(this, value);
      }

      connectedCallback() {
        // Preserve selectors used by older third-party plugin styles while
        // first-party markup uses the semantic custom element.
        this.classList.add("material-symbols-outlined");
        if (
          !this.hasAttribute("aria-hidden") &&
          !this.hasAttribute("aria-label") &&
          !this.hasAttribute("aria-labelledby")
        ) {
          this.setAttribute("aria-hidden", "true");
        }
        this.render();
      }

      attributeChangedCallback() {
        this.render();
      }

      render() {
        const name = this.name;
        if (this.textContent !== name) this.textContent = name;
      }
    },
  );
}
