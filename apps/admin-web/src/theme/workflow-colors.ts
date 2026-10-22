/** Keep workflow type accents readable on the dark editor surface. */
export function workflowAccent(color: string, dark: boolean): string {
  if (!dark) return color;
  const match = /^#([\da-f]{2})([\da-f]{2})([\da-f]{2})$/i.exec(color);
  if (!match) return color;
  const channels = match.slice(1).map((part) => Number.parseInt(part, 16));
  return `#${channels.map((value) => Math.round(value * 0.55 + 255 * 0.45).toString(16).padStart(2, '0')).join('')}`;
}

export function workflowButtonColors(color: string, background: string, dark: boolean) {
  if (!dark) return { color, background, borderColor: background };
  return { color: workflowAccent(color, true), background: '#26364a', borderColor: '#354359' };
}
