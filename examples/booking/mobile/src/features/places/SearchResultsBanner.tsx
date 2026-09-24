// Sticky banner rendered above FilterChips in the Home bottom sheet
// when the search agent replies with text but no action. Tap X →
// dismisses both the banner and the underlying query so the venue list
// returns to the unfiltered seed.
import { Pressable, Text, View } from "react-native";
import { Sparkles, X } from "lucide-react-native";

const BRAND_VIOLET = "#A672E0";
const MAX_LEN = 120;

interface Props {
  text: string;
  onClear: () => void;
}

export function SearchResultsBanner({ text, onClear }: Props) {
  const trimmed = text.length > MAX_LEN ? `${text.slice(0, MAX_LEN - 1).trimEnd()}…` : text;
  return (
    <View className="mx-4 mt-2 mb-1 flex-row items-center bg-paper-100 rounded-2xl px-3 py-2 border border-paper-500/60">
      <Sparkles size={14} color={BRAND_VIOLET} />
      <Text
        className="flex-1 text-ink-800 text-sm ml-2"
        numberOfLines={3}
      >
        {trimmed}
      </Text>
      <Pressable
        onPress={onClear}
        accessibilityRole="button"
        accessibilityLabel="Clear search"
        hitSlop={8}
        className="ml-2 w-7 h-7 items-center justify-center rounded-full"
      >
        <X size={14} color="#3A3A36" />
      </Pressable>
    </View>
  );
}
