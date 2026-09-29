export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("X-Steganalysis", "local");
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch("/api" + path, { ...options, headers });
  if (!response.ok) {
    const payload = await response
      .json()
      .catch(() => ({ detail: `HTTP ${response.status}` }));
    throw new Error(
      typeof payload.detail === "string"
        ? payload.detail
        : JSON.stringify(payload.detail),
    );
  }
  return response.json() as Promise<T>;
}
export const contentUrl = (
  caseId: string,
  artifactId: string,
  download = false,
) =>
  `/api/cases/${caseId}/artifacts/${artifactId}/content${download ? "?download=true" : ""}`;
export const bytes = (n: number) =>
  n < 1024
    ? `${n} B`
    : n < 1048576
      ? `${(n / 1024).toFixed(1)} KiB`
      : `${(n / 1048576).toFixed(1)} MiB`;
export const date = (value: string) =>
  new Date(value).toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
export const errorText = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "An unexpected error occurred. Please retry.";
