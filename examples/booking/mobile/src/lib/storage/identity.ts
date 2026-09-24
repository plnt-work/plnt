// Anonymous identity — matches web Atlas's pattern. A per-install
// user_id persisted in AsyncStorage (web Atlas keeps it in
// sessionStorage; mobile wants it to survive process restarts).
// session_id is per-process by default — newSession() rotates it.
import AsyncStorage from "@react-native-async-storage/async-storage";
import { getRandomBytes } from "expo-crypto";

const USER_KEY = "plnt.user_id";
const SESSION_KEY = "plnt.session_id";

function freshId(prefix: string): string {
  // expo-crypto.getRandomBytes is the only universally-available source
  // on both iOS and Android Hermes. globalThis.crypto is not reliable on
  // Android Hermes builds — the earlier "crypto is a global" assumption
  // crashed bootstrap.
  const arr = getRandomBytes(6);
  return `${prefix}-${Array.from(arr)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")}`;
}

export async function getOrCreateUserId(): Promise<string> {
  const existing = await AsyncStorage.getItem(USER_KEY);
  if (existing) return existing;
  const fresh = freshId("m");
  await AsyncStorage.setItem(USER_KEY, fresh);
  return fresh;
}

export async function getOrCreateSessionId(): Promise<string> {
  const existing = await AsyncStorage.getItem(SESSION_KEY);
  if (existing) return existing;
  const fresh = freshId("s");
  await AsyncStorage.setItem(SESSION_KEY, fresh);
  return fresh;
}

export async function rotateSessionId(): Promise<string> {
  const fresh = freshId("s");
  await AsyncStorage.setItem(SESSION_KEY, fresh);
  return fresh;
}
