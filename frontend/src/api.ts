/** Calls to the Parcels services and WebSocket commands. */
import type { HomeAssistant } from "./types.ts";

export const DOMAIN = "parcels";

/** Calls a `parcels.*` service; failures are thrown (not toasted) so the card can show them inline. */
export function callParcelsService(
  hass: HomeAssistant,
  service: string,
  data: Record<string, unknown>,
): Promise<unknown> {
  return hass.callService(DOMAIN, service, data, undefined, false);
}

/**
 * Calls a `parcels.*` service that answers with `{parcel_id}` (split and merge)
 * and returns that ID, or null when the answer has none. Failures are thrown.
 */
export async function callParcelsServiceForParcel(
  hass: HomeAssistant,
  service: string,
  data: Record<string, unknown>,
): Promise<string | null> {
  const result = await hass.callService(DOMAIN, service, data, undefined, false, true);
  const response = (result as { response?: unknown } | null | undefined)?.response;
  if (typeof response !== "object" || response === null) {
    return null;
  }
  const parcelId = (response as { parcel_id?: unknown }).parcel_id;
  return typeof parcelId === "string" && parcelId !== "" ? parcelId : null;
}

/** Sends a `parcels/…` WebSocket command, e.g. `callParcelsCommand(hass, "get", {parcel_id})`. */
export function callParcelsCommand<T>(
  hass: HomeAssistant,
  command: string,
  data: Record<string, unknown> = {},
): Promise<T> {
  return hass.callWS<T>({ ...data, type: `${DOMAIN}/${command}` });
}
