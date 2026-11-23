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
    assert.deepEqual(dialogs.sort(), ["add-dialog.ts", "details-dialog.ts", "return-dialog.ts"]);
    for (const name of dialogs) {
      const text = source(name);
      const header = text.indexOf('<div class="dialog-header">');
      const content = text.indexOf('<div class="dialog-content">');
      assert.ok(header >= 0 && content > header, `${name} has a header before its content`);
      assert.match(text.slice(header, content), /aria-label=\$\{STRINGS\.close\}/, name);
    }
  });
});

describe("the return dialog", () => {
  const text = source("return-dialog.ts");

  test("marks a return picked up, and undoes it, through the Parcels services", () => {
    assert.match(text, /picked \? "mark_return_picked_up" : "undo_return_picked_up"/);
    assert.match(text, /callParcelsService\(hass, service, \{ return_id: ret\.id \}\)/);
    const services = readFileSync(new URL("../../custom_components/parcels/services.yaml", import.meta.url), "utf8");
    for (const name of ["mark_return_picked_up", "undo_return_picked_up"]) {
      assert.match(services, new RegExp(`^${name}:\\n  fields:\\n    return_id:\\n      required: true$`, "m"), name);
    }
  });

  test("shows the return's ID for the Parcels actions, as a parcel's details do", () => {
    assert.match(text, /\$\{ret\.restricted \? nothing : row\(STRINGS\.returnId, ret\.id\)\}\n    <\/dl>`;/);
    assert.match(source("strings.ts"), /^ {2}returnId: "Return ID",$/m);
    const en = readFileSync(new URL("../../custom_components/parcels/translations/en.json", import.meta.url), "utf8");
    const services = JSON.parse(en).services;
    for (const name of ["mark_return_picked_up", "undo_return_picked_up"]) {
      const field = services[name].fields.return_id;
      assert.equal(field.name, "Return ID", name);
      assert.equal(field.description, "The ID of the return, from the return's details on the Parcels page.", name);
    }
  });

  test("offers the buttons by the return's rules, and Remove to admins only", () => {
    assert.match(text, /const mark = canMarkPickedUp\(ret, today\);/);
    assert.match(text, /const undo = canUndoPickedUp\(ret, today\);/);
    assert.match(text, /const admin = !ret\.restricted && this\.snapshot\?\.settings\.user_is_admin === true;/);
    assert.match(text, /if \(this\._mode === "remove" && admin\) \{/);
    assert.match(text, /\$\{admin\s+\? html`<button type="button" class="btn danger" data-mode="remove"/);
  });
});
