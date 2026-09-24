// Venue detail screen. Composes hero + about + services + team +
// reviews. Services/team/reviews are mock-first (lib/api/venues.ts);
// flip LIVE_MODE there when MA-P6 endpoints ship.
//
// Pinned action bar at the bottom: [Ask] + [Book now]. Ask routes to
// the assistant modal; Book opens the booking stack at /book/services.
import { Pressable, ScrollView, Text, View } from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { MessageCircle } from "lucide-react-native";

import { VenueHero } from "@/features/venue/VenueHero";
import { AboutSection } from "@/features/venue/AboutSection";
import { ServicesList } from "@/features/venue/ServicesList";
import { TeamGrid } from "@/features/venue/TeamGrid";
import { ReviewsList } from "@/features/venue/ReviewsList";

import { SAMPLE_BUSINESSES } from "@web/places/sample-businesses";

export default function VenueDetailScreen() {
  const { placeId } = useLocalSearchParams<{ placeId: string }>();
  const business = SAMPLE_BUSINESSES.find((b) => b.place_id === placeId);
  const insets = useSafeAreaInsets();

  if (!business) {
    return (
      <View className="flex-1 items-center justify-center bg-paper-100 px-6">
        <Text className="text-ink-800 text-base font-semibold">Venue not found</Text>
        <Text className="text-ink-200 text-sm mt-2 text-center">
          Place id <Text className="font-mono">{placeId}</Text> isn’t in the seed.
        </Text>
      </View>
    );
  }

  return (
    <View className="flex-1 bg-paper-100">
      <ScrollView
        className="flex-1"
        contentContainerStyle={{ paddingBottom: 96 + insets.bottom }}
      >
        <VenueHero business={business} />
        <AboutSection business={business} />
        <ServicesList placeId={business.place_id} />
        <TeamGrid placeId={business.place_id} />
        <ReviewsList placeId={business.place_id} />
      </ScrollView>

      {/* Pinned action bar */}
      <View
        className="absolute left-0 right-0 bottom-0 bg-white border-t border-paper-500/60 px-4 pt-3"
        style={{ paddingBottom: insets.bottom + 8 }}
      >
        <View className="flex-row gap-2">
          <Pressable
            onPress={() =>
              router.push({
                pathname: "/venue/[placeId]/assistant",
                params: { placeId: business.place_id },
              })
            }
            className="flex-row items-center justify-center gap-2 px-4 py-3 rounded-2xl bg-paper-200"
            accessibilityRole="button"
          >
            <MessageCircle size={16} color="#3A3A36" />
            <Text className="text-ink-800 font-semibold text-sm">Ask</Text>
          </Pressable>
          <Pressable
            onPress={() =>
              router.push({
                pathname: "/venue/[placeId]/book/services",
                params: { placeId: business.place_id },
              })
            }
            className="flex-1 items-center justify-center px-4 py-3 rounded-2xl bg-ink-800"
            accessibilityRole="button"
          >
            <Text className="text-paper-100 font-semibold text-sm">Book now</Text>
          </Pressable>
        </View>
      </View>
    </View>
  );
}
