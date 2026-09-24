// Top-of-screen overlay pill on Home. Two-line content: primary query
// (or "All treatments") + secondary location label. Tap-anywhere routes
// to /search. The right icon opens the filters drawer.
import { Pressable, Text, View } from "react-native";
import { Search, SlidersHorizontal } from "lucide-react-native";
import { router } from "expo-router";

interface Props {
  primary: string;
  secondary: string;
  onOpenFilters: () => void;
}

export function SearchPill({ primary, secondary, onOpenFilters }: Props) {
  return (
    <View
      className="flex-row items-center bg-white rounded-2xl px-3 py-2"
      style={{
        shadowColor: "#0E1116",
        shadowOpacity: 0.08,
        shadowRadius: 12,
        shadowOffset: { width: 0, height: 4 },
        elevation: 6,
      }}
    >
      <Pressable
        onPress={() => router.push("/search")}
        accessibilityRole="button"
        accessibilityLabel="Open search"
        className="flex-1 flex-row items-center"
      >
        <Search size={18} color="#3A3A36" />
        <View className="flex-1 ml-2">
          <Text numberOfLines={1} className="text-ink-800 text-sm font-semibold">
            {primary}
          </Text>
          <Text numberOfLines={1} className="text-ink-200 text-xs">
            {secondary}
          </Text>
        </View>
      </Pressable>
      <Pressable
        onPress={onOpenFilters}
        accessibilityRole="button"
        accessibilityLabel="Open filters"
        className="w-9 h-9 rounded-full bg-paper-200 items-center justify-center ml-2"
      >
        <SlidersHorizontal size={16} color="#3A3A36" />
      </Pressable>
    </View>
  );
}
