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

/** A parcel or a customer return that a notification's link asks to open. */
export interface DeepLink {
  readonly kind: "parcel" | "return";
  readonly id: string;
}

/** The query parameters of such links, with the IDs each accepts. */
const LINK_IDS: Readonly<Record<DeepLink["kind"], RegExp>> = {
  parcel: /^p_[0-9a-f]{1,64}$/,
  return: /^ret_[0-9a-f]{1,64}$/,
};

function isLinkKey(key: string): key is DeepLink["kind"] {
  return Object.hasOwn(LINK_IDS, key);
}

function decode(text: string): string {
  try {
    return decodeURIComponent(text.replaceAll("+", " "));
  } catch {
    return text;
  }
}

/** The `key=value` pairs of a query as written, without the `?`. */
function pairsOf(search: string): string[] {
  return search
    .replace(/^\?/, "")
    .split("&")
    .filter((pair) => pair !== "");
}

function keyOf(pair: string): string {
  const index = pair.indexOf("=");
  return decode(index < 0 ? pair : pair.slice(0, index));
}

/** The parcel or return a query (`location.search`) asks to open, if any. */
export function readDeepLink(search: string): DeepLink | null {
  for (const pair of pairsOf(search)) {
    const kind = keyOf(pair);
    if (!isLinkKey(kind)) {
      continue;
    }
    const index = pair.indexOf("=");
    const id = index < 0 ? "" : decode(pair.slice(index + 1));
    if (LINK_IDS[kind].test(id)) {
      return { kind, id };
    }
  }
  return null;
}

/**
 * The query without its links, keeping every other parameter as written
 * (`?kiosk` stays `?kiosk`); unchanged when it has no link.
 */
export function withoutDeepLink(search: string): string {
  const pairs = pairsOf(search);
  const kept = pairs.filter((pair) => !isLinkKey(keyOf(pair)));
  if (kept.length === pairs.length) {
    return search;
  }
  return kept.length ? `?${kept.join("&")}` : "";
}
