/**
 * Validation of the cards' YAML configuration. Unknown keys are ignored, since
 * Home Assistant adds its own (grid_options, visibility, view_layout…).
 */
import { STRINGS } from "./strings.ts";

export interface WeekCardConfig {
  type: string;
  /** undefined: the default title; "": no title. */
  title: string | undefined;
  show_archived: boolean;
}

export interface ListCardConfig {
  type: string;
  title: string | undefined;
}

export interface ReviewCardConfig {
  type: string;
  title: string | undefined;
}

type RawConfig = Record<string, unknown>;

function asObject(config: unknown): RawConfig {
  if (typeof config !== "object" || config === null || Array.isArray(config)) {
    throw new Error(STRINGS.configInvalid);
  }
  return config as RawConfig;
}

function title(config: RawConfig): string | undefined {
  const value = config.title;
  if (value === undefined || value === null) {
    return undefined;
  }
  if (typeof value !== "string") {
    throw new Error(STRINGS.configTitle);
  }
  return value.trim();
}

function type(config: RawConfig): string {
  return typeof config.type === "string" ? config.type : "";
}

export function weekCardConfig(config: unknown): WeekCardConfig {
  const raw = asObject(config);
  const showArchived = raw.show_archived ?? true;
  if (typeof showArchived !== "boolean") {
    throw new Error(STRINGS.configShowArchived);
  }
  return { type: type(raw), title: title(raw), show_archived: showArchived };
}

export function listCardConfig(config: unknown): ListCardConfig {
  const raw = asObject(config);
  return { type: type(raw), title: title(raw) };
}

export function reviewCardConfig(config: unknown): ReviewCardConfig {
  const raw = asObject(config);
  return { type: type(raw), title: title(raw) };
}

/** The title to show: the configured one, else the default; null for none. */
export function cardTitle(configured: string | undefined, fallback: string): string | null {
  if (configured === undefined) {
    return fallback;
  }
  return configured || null;
}
