/** Registration of the custom elements and of the cards in Home Assistant's card picker. */

export const DOCUMENTATION_URL = "https://github.com/fratei/ha-parcels";

interface CustomCardEntry {
  type: string;
  name: string;
  description: string;
  preview?: boolean;
  documentationURL?: string;
}

/** Defines the element unless another copy of the bundle already did. */
export function defineElement(name: string, element: CustomElementConstructor): void {
  if (!customElements.get(name)) {
    customElements.define(name, element);
  }
}

/** Lists the card in the card picker (once). */
export function registerCard(type: string, name: string, description: string): void {
  const host = window as unknown as { customCards?: unknown };
  if (!Array.isArray(host.customCards)) {
    host.customCards = [];
  }
  const cards = host.customCards as CustomCardEntry[];
  if (!cards.some((card) => card?.type === type)) {
    cards.push({ type, name, description, preview: true, documentationURL: DOCUMENTATION_URL });
  }
}
