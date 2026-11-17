import { STRINGS } from "./strings.ts";

/** The message of a WebSocket or service error (`error.message`), or a readable fallback. */
export function errorMessage(error: unknown): string {
  if (typeof error === "string" && error.trim()) {
    return error;
  }
  if (error && typeof error === "object") {
    const message = (error as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
    const code = (error as { code?: unknown }).code;
    if (typeof code === "string" && code.trim()) {
      return code;
    }
  }
  return STRINGS.unknownError;
}
