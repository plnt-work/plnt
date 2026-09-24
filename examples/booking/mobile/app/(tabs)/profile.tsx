// Profile — surfaces the anonymous user_id (so the user can copy it to
// support tickets) and a session "+ new" affordance mirroring web
// Atlas's SessionBar. No sign-in, no avatar. Yet.
import { useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { RefreshCw, User } from "lucide-react-native";

import { getOrCreateUserId, getOrCreateSessionId, rotateSessionId } from "@/lib/storage/identity";

export default function ProfileScreen() {
  const insets = useSafeAreaInsets();
  const [userId, setUserId] = useState<string>("");
  const [sessionId, setSessionId] = useState<string>("");

  useEffect(() => {
    (async () => {
      setUserId(await getOrCreateUserId());
      setSessionId(await getOrCreateSessionId());
    })();
  }, []);

  const onNewSession = async () => {
    const fresh = await rotateSessionId();
    setSessionId(fresh);
  };

  return (
    <View
      className="flex-1 bg-paper-100 px-4"
      style={{ paddingTop: insets.top + 12 }}
    >
      <View className="flex-row items-center gap-3 py-4">
        <View className="w-12 h-12 rounded-full bg-paper-300 items-center justify-center">
          <User size={22} color="#3A3A36" />
        </View>
        <View>
          <Text className="text-ink-800 text-base font-semibold">Anonymous</Text>
          <Text className="text-ink-200 text-xs">No sign-in yet</Text>
        </View>
      </View>

      <View className="mt-4 bg-white rounded-2xl border border-paper-500 p-4">
        <Text className="text-ink-200 text-xs uppercase tracking-wider">User id</Text>
        <Text selectable className="text-ink-800 text-sm font-mono mt-1">
          {userId || "—"}
        </Text>
        <Text className="text-ink-200 text-xs uppercase tracking-wider mt-4">Session id</Text>
        <Text selectable className="text-ink-800 text-sm font-mono mt-1">
          {sessionId || "—"}
        </Text>

        <Pressable
          onPress={onNewSession}
          className="flex-row items-center gap-2 self-start mt-4 px-3 py-2 bg-ink-800 rounded-full"
        >
          <RefreshCw size={14} color="#FBF7EE" />
          <Text className="text-paper-100 text-xs font-medium">New session</Text>
        </Pressable>
      </View>
    </View>
  );
}
