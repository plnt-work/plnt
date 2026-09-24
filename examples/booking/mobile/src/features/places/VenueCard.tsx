// Horizontal-FlashList card on Home; also reused inside the Explore
// bottom sheet. Routes tap → /venue/[placeId].
import { Pressable, Text, View } from "react-native";
import { Image } from "expo-image";
import { Star } from "lucide-react-native";
import { router } from "expo-router";
import type { Business } from "@web/places/types";
import { metaFor } from "@web/places/verticals";

interface Props {
  business: Business;
  width?: number;
  variant?: "horizontal" | "wide";
  /** When true, renders a brand-violet outline. Used by Home to mirror
   *  the selected marker without changing tap behavior. */
  highlighted?: boolean;
}

const BRAND_VIOLET = "#A672E0";

export function VenueCard({ business, width = 220, variant = "horizontal", highlighted = false }: Props) {
  const meta = metaFor(business.vertical);
  return (
    <Pressable
      style={{
        width: variant === "wide" ? undefined : width,
        borderColor: highlighted ? BRAND_VIOLET : "transparent",
        borderWidth: highlighted ? 2 : 0,
        borderRadius: 18,
        padding: highlighted ? 4 : 0,
      }}
      className={variant === "wide" ? "w-full mb-3" : "mr-3"}
      onPress={() =>
        router.push({ pathname: "/venue/[placeId]", params: { placeId: business.place_id } })
      }
    >
      <View className="rounded-2xl overflow-hidden bg-paper-200">
        <View className="aspect-[4/3] bg-paper-300 items-center justify-center">
          {business.photos?.[0] || business.photo_uri ? (
            <Image
              source={{ uri: business.photos?.[0] ?? business.photo_uri }}
              style={{ width: "100%", height: "100%" }}
              contentFit="cover"
              cachePolicy="memory-disk"
              transition={150}
            />
          ) : (
            <View
              className="w-12 h-12 rounded-full items-center justify-center"
              style={{ backgroundColor: meta.color }}
            >
              <Text className="text-white text-lg font-semibold">
                {business.display_name.slice(0, 1)}
              </Text>
            </View>
          )}
        </View>
      </View>
      <View className="pt-2">
        <Text numberOfLines={1} className="text-ink-800 font-semibold text-sm">
          {business.display_name}
        </Text>
        <View className="flex-row items-center gap-1 mt-1">
          <Star size={12} color="#C97B2A" fill="#C97B2A" />
          <Text className="text-ink-500 text-xs">
            {business.rating.toFixed(1)}
            <Text className="text-ink-200">  ·  {meta.label}</Text>
          </Text>
        </View>
        <Text numberOfLines={1} className="text-ink-200 text-xs mt-0.5">
          {business.address}
        </Text>
      </View>
    </Pressable>
  );
}
