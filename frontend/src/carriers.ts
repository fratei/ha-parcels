/** Carrier IDs and display names; keep in sync with CARRIER_NAMES in const.py. */
export const CARRIER_NAMES: Readonly<Record<string, string>> = {
  amazon: "Amazon Logistics",
  asendia: "Asendia",
  bpost: "bpost",
  brt: "BRT",
  cainiao: "Cainiao",
  chronopost: "Chronopost",
  colissimo: "Colissimo",
  correos: "Correos",
  correos_express: "Correos Express",
  ctt: "CTT",
  ctt_expresso: "CTT Expresso",
  deutsche_post: "Deutsche Post",
  dhl: "DHL",
  dpd: "DPD",
  evri: "Evri",
  fedex: "FedEx",
  gls: "GLS",
  hermes: "Hermes",
  inpost: "InPost",
  la_poste: "La Poste",
  mondial_relay: "Mondial Relay",
  mrw: "MRW",
  nacex: "Nacex",
  paack: "Paack",
  postnl: "PostNL",
  poste_italiane: "Poste Italiane",
  royal_mail: "Royal Mail",
  sda: "SDA",
  seur: "SEUR",
  tnt: "TNT",
  ups: "UPS",
  usps: "USPS",
  vinted_go: "Vinted Go",
  yunexpress: "YunExpress",
  other: "Other",
};

/** Carrier options for pickers, sorted by name, with "Other" last. */
export function carrierOptions(): Array<{ id: string; name: string }> {
  return Object.entries(CARRIER_NAMES)
    .filter(([id]) => id !== "other")
    .map(([id, name]) => ({ id, name }))
    .sort((a, b) => a.name.localeCompare(b.name, "en", { sensitivity: "base" }))
    .concat([{ id: "other", name: CARRIER_NAMES["other"] ?? "Other" }]);
}

/** Display name for a carrier ID; unknown IDs are returned unchanged. */
export function carrierName(id: string): string {
  return Object.hasOwn(CARRIER_NAMES, id) ? (CARRIER_NAMES[id] ?? id) : id;
}
