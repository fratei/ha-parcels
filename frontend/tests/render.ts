/**
 * A rough HTML text of a lit template, for tests without a DOM: bindings are
 * filled in and class and style maps written out; listeners, properties and
 * attributes bound to `nothing` are left out. Whitespace is collapsed.
 */
import { noChange, nothing } from "lit";
import { classMap } from "lit/directives/class-map.js";
import { styleMap } from "lit/directives/style-map.js";

interface Template {
  strings: readonly string[];
  values: readonly unknown[];
}

interface Directive {
  _$litDirective$: unknown;
  values: readonly unknown[];
}

const CLASS_MAP = (classMap({}) as unknown as Directive)._$litDirective$;
const STYLE_MAP = (styleMap({}) as unknown as Directive)._$litDirective$;
const BINDING = /\s([.?@]?)([\w-]+)=$/;

function isTemplate(value: unknown): value is Template {
  return typeof value === "object" && value !== null && "strings" in value && "values" in value;
}

function isDirective(value: unknown): value is Directive {
  return typeof value === "object" && value !== null && "_$litDirective$" in value;
}

function empty(value: unknown): boolean {
  return value === nothing || value === noChange || value === null || value === undefined;
}

function directiveText(value: Directive): string {
  const info = Object.entries((value.values[0] ?? {}) as Record<string, unknown>);
  if (value._$litDirective$ === CLASS_MAP) {
    return info
      .filter(([, on]) => Boolean(on))
      .map(([name]) => name)
      .join(" ");
  }
  if (value._$litDirective$ === STYLE_MAP) {
    return info
      .filter(([, style]) => !empty(style))
      .map(([name, style]) => `${name}: ${String(style)}`)
      .join("; ");
  }
  return "";
}

function text(value: unknown): string {
  if (empty(value) || typeof value === "function" || typeof value === "boolean") {
    return "";
  }
  if (Array.isArray(value)) {
    return value.map(text).join("");
  }
  if (isDirective(value)) {
    return directiveText(value);
  }
  if (!isTemplate(value)) {
    return String(value);
  }
  let out = value.strings[0] ?? "";
  value.values.forEach((part, index) => {
    const binding = BINDING.exec(out);
    if (binding) {
      out = out.slice(0, binding.index);
      const [, prefix, name] = binding;
      if (prefix === "?" && part) {
        out += ` ${name}`;
      } else if (prefix === "" && !empty(part)) {
        out += ` ${name}="${text(part)}"`;
      }
    } else {
      out += text(part);
    }
    out += value.strings[index + 1] ?? "";
  });
  return out;
}

/** The template as HTML text, e.g. `<span class="chip-title">Example Shop</span>`. */
export function renderText(value: unknown): string {
  return text(value)
    .replace(/\s+/g, " ")
    .replace(/\s+>/g, ">")
    .trim();
}
