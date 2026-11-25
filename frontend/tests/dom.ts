/**
 * Lets the card modules load in node: lit's node build provides customElements and
 * HTMLElement, and registerCard() also needs window. Import this before any card module.
 */
const host = globalThis as unknown as { window?: unknown };
host.window ??= globalThis;
