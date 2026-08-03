/**
 * Build the shared three-bubble loading indicator.
 *
 * The caller owns status text and ARIA live-region behavior so this visual can
 * be reused inside an existing status container without duplicate announcements.
 */
export function createThreeBubbleLoader({ active = true } = {}) {
  const loader = document.createElement("span");
  loader.className = "three-bubble-loader";
  loader.classList.toggle("is-active", active);
  loader.setAttribute("aria-hidden", "true");

  for (let index = 0; index < 3; index += 1) {
    const bubble = document.createElement("span");
    bubble.className = "three-bubble-loader-dot";
    loader.appendChild(bubble);
  }

  return loader;
}
