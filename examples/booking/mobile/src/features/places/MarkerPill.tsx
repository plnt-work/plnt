// Custom <Marker> child — dark rounded pill with rating + vertical
// icon. Selected gets a brand-violet outline and a 1.10 scale; tap is
// handled by the parent <Marker onPress>, not this component.
import { Text, View } from "react-native";
import { iconForVertical } from "./categories";
import type { Business } from "@web/places/types";

interface Props {
  business: Business;
  selected: boolean;
}

const BRAND_VIOLET = "#A672E0"; // token: colors.iri.violet
const INK = "#0E1116";          // token: colors.ink.800

export function MarkerPill({ business, selected }: Props) {
  const Icon = iconForVertical(business.vertical);
  return (
    <View
      style={{ transform: [{ scale: selected ? 1.1 : 1.0 }] }}
      className={
        "flex-row items-center gap-1 px-2 py-1 rounded-full " +
        (selected ? "border-2" : "")
      }
      // Inline because dynamic ring color isn't worth a nativewind cycle.
      // Background stays ink-800 even when selected; outline does the work.
    >
      <View
        style={{
          flexDirection: "row",
          alignItems: "center",
          backgroundColor: INK,
          borderColor: selected ? BRAND_VIOLET : "transparent",
          borderWidth: selected ? 2 : 0,
          borderRadius: 999,
          paddingHorizontal: 8,
          paddingVertical: 4,
        }}
      >
        <Icon size={12} color="#FBF7EE" />
        <Text className="text-paper-100 text-xs font-semibold ml-1">
          {business.rating.toFixed(1)}
        </Text>
      </View>
    </View>
  );
}
