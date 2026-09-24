// /search — modal-presented full-screen text input. Submits a query
// into the shared search store; Home subscribes and fires the WS
// dispatch from there (one WS connection per process). Cancel just
// dismisses.
import { useState } from "react";
import { Pressable, Text, TextInput, View } from "react-native";
import { router } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Search, X } from "lucide-react-native";

import { setSearch, useSearch } from "@/features/search/store";

export default function SearchScreen() {
  const insets = useSafeAreaInsets();
  const current = useSearch();
  const [value, setValue] = useState<string>(current.query ?? "");

  const submit = () => {
    const trimmed = value.trim();
    setSearch({ query: trimmed || null });
    router.back();
  };

  const clear = () => {
    setValue("");
    setSearch({ query: null });
  };

  return (
    <View className="flex-1 bg-paper-100" style={{ paddingTop: insets.top + 8 }}>
      <View className="flex-row items-center px-4 gap-2">
        <Pressable
          onPress={() => router.back()}
          className="w-9 h-9 rounded-full bg-paper-200 items-center justify-center"
          accessibilityRole="button"
          accessibilityLabel="Cancel"
        >
          <X size={18} color="#3A3A36" />
        </Pressable>
        <View className="flex-1 flex-row items-center bg-white border border-paper-500 rounded-2xl px-3">
          <Search size={18} color="#3A3A36" />
          <TextInput
            value={value}
            onChangeText={setValue}
            autoFocus
            placeholder="Try “haircut tonight”"
            placeholderTextColor="#9A968C"
            returnKeyType="search"
            onSubmitEditing={submit}
            className="flex-1 text-ink-800 text-base ml-2 py-2"
          />
          {value.length > 0 ? (
            <Pressable onPress={clear} accessibilityRole="button" accessibilityLabel="Clear">
              <X size={16} color="#9A968C" />
            </Pressable>
          ) : null}
        </View>
      </View>

      <View className="px-4 mt-6">
        <Text className="text-ink-200 text-xs uppercase tracking-wider">Suggestions</Text>
        <Text className="text-ink-200 text-sm mt-2">
          Recent and suggested queries land here when MA-P6 ships. Tap the keyboard
          search key to dispatch as a freeform turn (classify_intent on the WS).
        </Text>
      </View>
    </View>
  );
}
