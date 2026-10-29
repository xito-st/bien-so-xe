const CSRF_STORAGE_KEY = "biensoxe_csrf_token";

export function getCsrfToken(): string {
  return sessionStorage.getItem(CSRF_STORAGE_KEY) || "";
}

export function setCsrfToken(token: string | null | undefined): void {
  if (token) {
    sessionStorage.setItem(CSRF_STORAGE_KEY, token);
  } else {
    sessionStorage.removeItem(CSRF_STORAGE_KEY);
  }
}

export class ApiError extends Error {
  status: number;
  code?: string;
  data?: unknown;

  constructor(status: number, message: string, code?: string, data?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.data = data;
  }
}

export async function apiRequest<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});
  const csrf = getCsrfToken();
  if (csrf) {
    headers.set("X-CSRF-Token", csrf);
  }
  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "include",
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const payload = await response.json();
    if (!response.ok) {
      const detail = payload?.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : detail?.message || payload?.message || `Lỗi HTTP ${response.status}`;
      const code = typeof detail === "object" ? detail?.code : payload?.code;
      throw new ApiError(response.status, msg, code, payload);
    }
    if (payload?.csrf_token) {
      setCsrfToken(payload.csrf_token);
    }
    return payload as T;
  }

  if (!response.ok) {
    const text = await response.text();
    throw new ApiError(response.status, text || `Lỗi HTTP ${response.status}`);
  }

  return (await response.blob()) as unknown as T;
}

export function formatDateTimeVN(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("vi-VN", {
    timeZone: "Asia/Ho_Chi_Minh",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

