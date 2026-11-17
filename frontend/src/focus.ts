/** Keeps keyboard focus inside a modal dialog. */

const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function focusableIn(container: HTMLElement): HTMLElement[] {
  return [...container.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
    (element) => !element.closest("[hidden], [inert]") && element.getClientRects().length > 0,
  );
}

/**
 * On Tab or Shift+Tab, wraps focus from the last focusable element to the
 * first one and back, so it never leaves the container.
 */
export function trapFocus(event: KeyboardEvent, container: HTMLElement): void {
  if (event.key !== "Tab" || event.altKey || event.ctrlKey || event.metaKey) {
    return;
  }
  const elements = focusableIn(container);
  const first = elements[0];
  const last = elements[elements.length - 1];
  if (!first || !last) {
    event.preventDefault();
    container.focus();
    return;
  }
  const root = container.getRootNode() as Document | ShadowRoot;
  const active = root.activeElement;
  const inside = active instanceof HTMLElement && container.contains(active) && active !== container;
  if (event.shiftKey && (!inside || active === first)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && (!inside || active === last)) {
    event.preventDefault();
    first.focus();
  }
}
