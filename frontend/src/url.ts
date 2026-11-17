/**
 * Returns the URL as a string when it's a well-formed https: URL without
 * credentials, otherwise null, so that only safe links are ever rendered.
 */
export function safeHttpsUrl(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    return null;
  }
  if (url.protocol !== "https:" || !url.hostname || url.username || url.password) {
    return null;
  }
  return url.href;
}
