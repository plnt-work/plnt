// Expo push token registration.
//
// Best-effort — never throw to the caller. On permission denial, missing
// projectId, or a bad network hop we log and return null so the app boots
// unaffected. Downstream: MA-P6's POST /v1/push/register stores the token
// per (tenant, user) so the backend can send booking updates.
//
// Call `configureNotifications()` once at boot (sets the foreground handler)
// then `registerPushToken(tenantId, userId)` after we have both ids.
import * as Notifications from "expo-notifications";
import Constants from "expo-constants";
import { Platform } from "react-native";
import { env } from "@/lib/env";

/** Foreground notification presentation. Called once at module load /
 *  app boot — safe to call multiple times, it just overwrites the handler. */
export function configureNotifications(): void {
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowAlert: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
      // SDK 51+ handler shape — these two supersede shouldShowAlert on
      // newer expo-notifications versions but are additive on older ones.
      shouldShowBanner: true,
      shouldShowList: true,
    }),
  });
}

function resolveProjectId(): string | undefined {
  // EAS project id is the canonical source; fall back to slug for
  // dev-client where the extra.eas block hasn't been filled in yet.
  const extra = Constants.expoConfig?.extra as
    | { eas?: { projectId?: string } }
    | undefined;
  return extra?.eas?.projectId ?? Constants.expoConfig?.slug;
}

/**
 * Request notification permission, fetch the Expo push token, and
 * register it with the backend. Returns the token on success, null
 * otherwise. Never throws.
 */
export async function registerPushToken(
  tenantId: string,
  userId: string,
): Promise<string | null> {
  try {
    // Android needs a channel before any notifications will present.
    if (Platform.OS === "android") {
      await Notifications.setNotificationChannelAsync("default", {
        name: "default",
        importance: Notifications.AndroidImportance.DEFAULT,
      });
    }

    const perm = await Notifications.requestPermissionsAsync();
    if (!perm.granted) {
      // User denied. Return null quietly — they can re-enable in settings
      // and the next app boot will retry.
      return null;
    }

    const projectId = resolveProjectId();
    if (!projectId) {
      console.warn(
        "[push] no EAS projectId resolved from expoConfig.extra.eas.projectId; " +
          "push token fetch will likely fail on dev-client builds",
      );
    }

    const tokenRes = await Notifications.getExpoPushTokenAsync(
      projectId ? { projectId } : undefined,
    );
    const expoToken = tokenRes.data;
    if (!expoToken) return null;

    const platform: "ios" | "android" =
      Platform.OS === "ios" ? "ios" : "android";

    const url = `${env.apiBase.replace(/\/$/, "")}/v1/push/register`;
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        tenant_id: tenantId,
        user_id: userId,
        expo_token: expoToken,
        platform,
      }),
    });
    if (!res.ok) {
      console.warn(
        `[push] register failed: ${res.status} ${await res
          .text()
          .catch(() => "")}`,
      );
      return null;
    }
    return expoToken;
  } catch (err) {
    console.warn("[push] registerPushToken error:", err);
    return null;
  }
}
