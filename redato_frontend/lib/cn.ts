/**
 * Util mínimo de className. Sem dependência externa.
 */
export function cn(
  ...args: Array<string | false | null | undefined>
): string {
  return args.filter(Boolean).join(" ");
}
