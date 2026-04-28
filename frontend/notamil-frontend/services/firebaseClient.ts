import { initializeApp, getApps } from 'firebase/app';
import { getAuth, type Auth } from 'firebase/auth';
import { mockAuth } from './mockAuthState';

const OFFLINE = process.env.NEXT_PUBLIC_DEV_OFFLINE === '1';

let app: ReturnType<typeof initializeApp> | null = null;
let auth: Auth | typeof mockAuth | null = null;

if (typeof window !== 'undefined') {
  if (OFFLINE) {
    // In offline mode skip Firebase init entirely; export the mock auth.
    auth = mockAuth;
  } else {
    const firebaseConfig = {
      apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
      authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
      projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
      storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
      messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
      appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
    };

    console.log('Firebase Config:', {
      ...firebaseConfig,
      apiKey: firebaseConfig.apiKey ? '**exists**' : '**missing**'
    });

    if (!getApps().length) {
      app = initializeApp(firebaseConfig);
    } else {
      app = getApps()[0];
    }
    auth = getAuth(app);
  }
}

export { auth };
