export function getInitials(fullName?: string): string {
  if (!fullName) return "";
  return fullName
    .split(" ")
    .map((w) => w[0])
    .join("");
}