/**
 * Shared state + helpers for the offline mock auth. Lives in its own module
 * so both ``firebaseClient`` and ``authSdk`` can import from it without a
 * circular dependency.
 */

export type MockUser = {
  uid: string;
  email: string;
  displayName: string;
  getIdToken: () => Promise<string>;
};

export type MockAuth = {
  currentUser: MockUser | null;
};

export type MockClaims = {
  uid: string;
  email: string;
  role: string;
  name: string;
};

export const MOCK_USER_STORAGE_KEY = "redato_dev_mock_user";

export const mockAuth: MockAuth = { currentUser: null };

function base64UrlEncode(input: string): string {
  const b64 =
    typeof window === "undefined"
      ? Buffer.from(input, "utf-8").toString("base64")
      : btoa(unescape(encodeURIComponent(input)));
  return b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function makeDevToken(claims: MockClaims): string {
  return `dev:${base64UrlEncode(JSON.stringify(claims))}`;
}

export function makeMockUser(claims: MockClaims): MockUser {
  return {
    uid: claims.uid,
    email: claims.email,
    displayName: claims.name,
    async getIdToken() {
      return makeDevToken(claims);
    },
  };
}

export function persistMockUser(claims: MockClaims): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(MOCK_USER_STORAGE_KEY, JSON.stringify(claims));
}

export function hydrateMockUser(): void {
  if (typeof window === "undefined") return;
  try {
    const raw = window.localStorage.getItem(MOCK_USER_STORAGE_KEY);
    if (!raw) return;
    const claims = JSON.parse(raw);
    if (claims?.uid && claims?.email && claims?.role) {
      mockAuth.currentUser = makeMockUser(claims);
    }
  } catch {
    // ignore malformed persisted state
  }
}
