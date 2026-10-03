// Colour follows the chain, never its rank: fixed slot per chain.
export const CHAIN_SLOT: Record<string, number> = {
  shufersal: 1,
  rami_levy: 2,
  osher_ad: 3,
  yohananof: 4,
  tiv_taam: 5,
};

export function chainColor(chainKey: string): string {
  return `var(--series-${CHAIN_SLOT[chainKey] ?? 6})`;
}
