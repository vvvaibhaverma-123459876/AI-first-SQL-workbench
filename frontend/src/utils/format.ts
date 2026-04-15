export function titleCase(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase())
}
