import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { describe, test } from "node:test";

const SRC = new URL("../src/", import.meta.url);

function source(name: string): string {
  return readFileSync(new URL(name, SRC), "utf8");
}

/** The text of the dialogStyles template in styles.ts. */
function dialogCss(): string {
  const text = source("styles.ts");
  const start = text.indexOf("export const dialogStyles = css`");
  assert.ok(start >= 0, "dialogStyles was found");
  const end = text.indexOf("`;", start);
  return text.slice(start, end);
}

/** The rules inside the media query that makes dialogs full screen. */
function fullScreenCss(): string {
  const css = dialogCss();
  const match = /@media \(max-width: 600px\), \(max-height: 500px\) \{/.exec(css);
  assert.ok(match, "dialogs go full screen on narrow and on short screens");
  return css.slice(match.index);
}

const SIDES = ["top", "right", "bottom", "left"] as const;

describe("dialogs on phones", () => {
  test("a full-screen dialog keeps clear of the status bar and the home indicator", () => {
    const css = fullScreenCss();
    for (const side of SIDES) {
      assert.match(
        dialogCss(),
        new RegExp(
          `--parcels-inset-${side}: var\\(--safe-area-inset-${side}, env\\(safe-area-inset-${side}, 0px\\)\\)`,
        ),
        `the ${side} inset follows Home Assistant's and the browser's safe area`,
      );
      assert.match(css, new RegExp(`padding-${side}: var\\(--parcels-inset-${side}\\)`), side);
    }
    assert.match(css, /height: 100dvh/);
  });

  test("a centred dialog fits inside the safe area", () => {
    assert.match(
      dialogCss(),
      /max-height: calc\(100dvh - 32px - var\(--parcels-inset-top\) - var\(--parcels-inset-bottom\)\)/,
    );
  });

  test("every dialog has its close button in the header, outside the scrolling content", () => {
    const dialogs = readdirSync(SRC)
      .filter((name) => name.endsWith(".ts"))
      .filter((name) => /extends ParcelsDialogBase\b/.test(source(name)));
    assert.deepEqual(dialogs.sort(), ["add-dialog.ts", "details-dialog.ts"]);
    for (const name of dialogs) {
      const text = source(name);
      const header = text.indexOf('<div class="dialog-header">');
      const content = text.indexOf('<div class="dialog-content">');
      assert.ok(header >= 0 && content > header, `${name} has a header before its content`);
      assert.match(text.slice(header, content), /aria-label=\$\{STRINGS\.close\}/, name);
    }
  });
});
