import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { describe, test } from "node:test";

const SRC = new URL("../src/", import.meta.url);
const sources = readdirSync(SRC)
  .filter((name) => name.endsWith(".ts"))
  .map((name) => ({ name, text: readFileSync(new URL(name, SRC), "utf8") }));

function findAll(patterns: RegExp[]): string[] {
  return sources.flatMap(({ name, text }) =>
    patterns.filter((pattern) => pattern.test(text)).map((pattern) => `${name}: ${pattern.source}`),
  );
}

describe("source safety", () => {
  test("never turns strings into markup or code", () => {
    assert.ok(sources.some(({ name }) => name === "index.ts"), "the sources were found");
    assert.deepEqual(
      findAll([
        /\binnerHTML\b/,
        /\bouterHTML\b/,
        /\binsertAdjacentHTML\b/,
        /\bsetHTMLUnsafe\b/,
        /\bcreateContextualFragment\b/,
        /\bDOMParser\b/,
        /\bunsafe(?:HTML|SVG|MathML|CSS|Static)\b/,
        /\bdocument\.write/,
        /\beval\s*\(/,
        /\bnew\s+Function\s*\(/,
      ]),
      [],
    );
  });

  test("makes no requests of its own", () => {
    assert.deepEqual(
      findAll([
        /\bfetch\s*\(/,
        /\bXMLHttpRequest\b/,
        /\bnew\s+(?:WebSocket|EventSource)\b/,
        /\bsendBeacon\b/,
        /\bimport\s*\(/,
        /@import\b/,
        /\burl\s*\(/,
        /<(?:img|link|script|iframe|object|embed)\b/,
      ]),
      [],
    );
  });

  test("links open in a new tab without an opener and only to checked URLs", () => {
    const anchors = sources.flatMap(({ name, text }) =>
      [...text.matchAll(/<a\b[^>]*>/g)].map((match) => ({ name, text, tag: match[0] })),
    );
    assert.ok(anchors.length > 0);
    for (const { name, text, tag } of anchors) {
      assert.match(tag, /\btarget="_blank"/, name);
      assert.match(tag, /\brel="noopener noreferrer"/, name);
      const binding = /\bhref=\$\{(\w+)\}/.exec(tag)?.[1];
      assert.ok(binding, `${name}: href must be a plain variable`);
      assert.match(text, new RegExp(`\\bconst ${binding} = [^;]*\\bsafeHttpsUrl\\(`), name);
    }
  });
});
