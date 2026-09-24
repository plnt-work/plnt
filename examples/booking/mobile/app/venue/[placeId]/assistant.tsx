// /venue/[placeId]/assistant — modal-presented chat sheet. Each open
// gets a fresh sessionId so a brand-new ConversationWorkflow spins up
// per ask. The actual UI lives in AssistantSheet.
import { useEffect, useMemo, useState } from "react";
import { Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";
import { BottomSheetModalProvider } from "@gorhom/bottom-sheet";

import { AssistantSheet } from "@/features/booking/AssistantSheet";
import { getOrCreateUserId } from "@/lib/storage/identity";
import { SAMPLE_BUSINESSES } from "@web/places/sample-businesses";
import { useSearch } from "@/features/search/store";

function freshSessionId(): string {
  const arr = new Uint8Array(6);
  (globalThis as unknown as {
    crypto: { getRandomValues(a: Uint8Array): void };
  }).crypto.getRandomValues(arr);
  return `assist-${Array.from(arr).map((b) => b.toString(16).padStart(2, "0")).join("")}`;
}

export default function AssistantScreen() {
  const { placeId } = useLocalSearchParams<{ placeId: string }>();
  const business = useMemo(
    () => SAMPLE_BUSINESSES.find((b) => b.place_id === placeId) ?? null,
    [placeId],
  );
  const { userLoc } = useSearch();

  const [userId, setUserId] = useState<string | null>(null);
  // Fresh sessionId per mount — keeps the ConversationWorkflow scoped
  // to this assistant invocation (matches the "new chat" pattern web
  // Atlas's SessionBar "+ new" button uses).
  const [sessionId] = useState<string>(() => freshSessionId());

  useEffect(() => {
    getOrCreateUserId().then(setUserId);
  }, []);

  if (!business || !userId) {
    return (
      <View className="flex-1 bg-black/40 items-center justify-center">
        <Text className="text-white text-sm">Loading…</Text>
      </View>
    );
  }

  return (
    <BottomSheetModalProvider>
      <AssistantSheet
        business={business}
        userId={userId}
        sessionId={sessionId}
        userLoc={userLoc}
      />
    </BottomSheetModalProvider>
  );
}
