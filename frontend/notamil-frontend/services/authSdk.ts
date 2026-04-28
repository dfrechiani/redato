/**
 * Auth SDK wrapper.
 *
 * - In normal mode, delegates ``signInWithEmailAndPassword`` to Firebase.
 * - In dev-offline mode (NEXT_PUBLIC_DEV_OFFLINE=1), provides an in-browser
 *   mock that signs in seed users with password ``redato123`` and fabricates
 *   a ``dev:<base64>`` token that the backend stub decodes.
 *
 * Login pages import from this module instead of ``firebase/auth`` so the
 * same code runs in both modes.
 */

import {
  mockAuth,
  makeMockUser,
  persistMockUser,
  hydrateMockUser,
  type MockUser,
} from "./mockAuthState";

const OFFLINE = process.env.NEXT_PUBLIC_DEV_OFFLINE === "1";

// Hydrate mockAuth from localStorage on first import in the browser so
// authFetch still works after a page reload.
if (OFFLINE) {
  hydrateMockUser();
}

type SeedUser = { uid: string; role: string; name: string };

const SEED_USERS: Record<string, SeedUser> = {
  "aluno@demo.redato": {
    uid: "student-demo-uid",
    role: "student",
    name: "Aluno Demo",
  },
  "professor@demo.redato": {
    uid: "prof-demo-uid",
    role: "professor",
    name: "Professor Demo",
  },
  "admin@demo.redato": {
    uid: "admin-demo-uid",
    role: "school_admin",
    name: "Admin Demo",
  },
};

const DEMO_PASSWORD = "redato123";

async function mockSignIn(email: string, password: string) {
  const seed = SEED_USERS[email.toLowerCase()];
  if (!seed) {
    throw Object.assign(new Error("auth/user-not-found"), {
      code: "auth/user-not-found",
    });
  }
  if (password !== DEMO_PASSWORD) {
    throw Object.assign(new Error("auth/wrong-password"), {
      code: "auth/wrong-password",
    });
  }

  const claims = {
    uid: seed.uid,
    email,
    role: seed.role,
    name: seed.name,
  };
  const mockUser = makeMockUser(claims);
  mockAuth.currentUser = mockUser;
  persistMockUser(claims);
  return { user: mockUser };
}

/**
 * Drop-in replacement for ``firebase/auth.signInWithEmailAndPassword``.
 * When online, delegates to the real Firebase SDK. When offline, authenticates
 * against the hardcoded seed users.
 */
export async function signInWithEmailAndPassword(
  authArg: unknown,
  email: string,
  password: string
): Promise<{ user: MockUser | import("firebase/auth").User }> {
  if (OFFLINE) {
    return mockSignIn(email, password);
  }
  // Lazy import so the firebase/auth bundle is only pulled in when needed.
  const { signInWithEmailAndPassword: real } = await import("firebase/auth");
  return real(authArg as import("firebase/auth").Auth, email, password);
}

export { OFFLINE as IS_OFFLINE, DEMO_PASSWORD, SEED_USERS };
