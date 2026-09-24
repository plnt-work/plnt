// Sheet sticky-header chip row. Three control chips (placeholders for
// menus that land when MA-P6 sort/filter endpoints ship) plus the
// vertical scroll row of category chips that DO mutate the filter.
import { Pressable, ScrollView, Text, View } from "react-native";
import { ChevronDown, SlidersHorizontal } from "lucide-react-native";
import { CATEGORIES } from "./categories";

interface Props {
  activeKey: string;
  onPickCategory: (key: string) => void;
  onOpenFilters: () => void;
}

const BRAND_VIOLET = "#A672E0";

function ControlChip({ label, onPress }: { label: string; onPress?: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      className="flex-row items-center gap-1 px-3 py-1.5 mr-2 bg-paper-200 rounded-full"
    >
      <Text className="text-ink-800 text-xs font-medium">{label}</Text>
      <ChevronDown size={12} color="#3A3A36" />
    </Pressable>
  );
}

export function FilterChips({ activeKey, onPickCategory, onOpenFilters }: Props) {
  return (
    <View className="px-4 pt-2 pb-3 bg-white border-b border-paper-500/60">
      {/* Row 1 — control chips */}
      <View className="flex-row items-center mb-3">
        <Pressable
          onPress={onOpenFilters}
          className="w-8 h-8 mr-2 rounded-full bg-ink-800 items-center justify-center"
          accessibilityRole="button"
          accessibilityLabel="Open filters"
        >
          <SlidersHorizontal size={14} color="#FBF7EE" />
        </Pressable>
        <ControlChip label="Venues" />
        <ControlChip label="Best match" />
        <ControlChip label="Price" />
      </View>

      {/* Row 2 — vertical chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        {CATEGORIES.map((c) => {
          const active = c.key === activeKey;
          const Icon = c.icon;
          return (
            <Pressable
              key={c.key}
              onPress={() => onPickCategory(c.key)}
              style={{
                backgroundColor: active ? BRAND_VIOLET : "#F8F2E0",
              }}
              className="flex-row items-center gap-1 px-3 py-1.5 mr-2 rounded-full"
            >
              <Icon size={12} color={active ? "#FFFFFF" : "#3A3A36"} />
              <Text
                className={
                  "text-xs font-medium " +
                  (active ? "text-white" : "text-ink-800")
                }
              >
                {c.label}
              </Text>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}
