const COLLAPSE_MAX_HEIGHT_EM = 15;
const UNMEASURABLE_WIDTH_PX = 1;

function pixels(value) {
  const parsed = Number.parseFloat(value || "0");
  return Number.isFinite(parsed) ? parsed : 0;
}

function hasUsableContentWidth(element, style = getComputedStyle(element)) {
  const contentWidth =
    element.clientWidth - pixels(style.paddingLeft) - pixels(style.paddingRight);
  return contentWidth > UNMEASURABLE_WIDTH_PX;
}

/**
 * Measure whether a message body exceeds its collapsed preview.
 *
 * Returns null while the surrounding chat has no usable layout. Replay can be
 * rendered in a hidden or zero-width staging tree, where ordinary text wraps
 * once per character and would otherwise produce a false overflow result.
 */
export function measureMessageCollapseOverflow(
  content,
  { expanded = false, lazy = false } = {},
) {
  if (lazy) return true;
  if (!content?.isConnected) return null;

  const history = content.closest?.("#chat-history");
  if (history && !hasUsableContentWidth(history)) {
    return null;
  }

  const style = getComputedStyle(content);
  if (!hasUsableContentWidth(content, style)) return null;

  const fontSize = Number.parseFloat(style.fontSize || "16") || 16;
  const maxHeight = expanded
    ? fontSize * COLLAPSE_MAX_HEIGHT_EM
    : content.clientHeight;

  return content.scrollHeight > maxHeight;
}
