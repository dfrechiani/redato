import { auth } from "./firebaseClient";

/**
 * Wraps fetch and attaches the current Firebase user's ID token as a Bearer
 * Authorization header. Use this for any call to an endpoint that requires
 * authentication (e.g. /manager/*, /intelligence/tutor, POST feedback).
 *
 * Throws if there's no authenticated user — callers should catch and route
 * the user back to login.
 */
export async function authFetch(
  input: RequestInfo | URL,
  init: RequestInit = {}
): Promise<Response> {
  const currentUser = auth?.currentUser;
  if (!currentUser) {
    throw new Error("Sessão expirada. Faça login novamente.");
  }
  const idToken = await currentUser.getIdToken();

  const headers = new Headers(init.headers || {});
  headers.set("Authorization", `Bearer ${idToken}`);
  if (!headers.has("Content-Type") && init.body && typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }

  return fetch(input, { ...init, headers });
}
