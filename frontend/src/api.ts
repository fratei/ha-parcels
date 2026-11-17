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

/** Sends a `parcels/…` WebSocket command, e.g. `callParcelsCommand(hass, "get", {parcel_id})`. */
export function callParcelsCommand<T>(
  hass: HomeAssistant,
  command: string,
  data: Record<string, unknown> = {},
): Promise<T> {
  return hass.callWS<T>({ ...data, type: `${DOMAIN}/${command}` });
}
