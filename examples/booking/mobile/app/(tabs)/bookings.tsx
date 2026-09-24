// Bookings tab — real list backed by GET /v1/users/:uid/bookings
// (mock-backed until LIVE_MODE flips). Two sections: Upcoming / Past.
// Empty state CTA → Home.
import { useEffect, useState } from "react";
import { Pressable, Text, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { Calendar, ChevronRight } from "lucide-react-native";

import { fetchUserBookings, type BookingSummary } from "@/lib/api/bookings";
import { getOrCreateUserId } from "@/lib/storage/identity";

type Row =
  | { kind: "header"; label: string }
  | { kind: "booking"; booking: BookingSummary };

function priceLabel(cents: number): string {
  return `₹${(cents / 100).toFixed(0)}`;
}

export default function BookingsScreen() {
  const insets = useSafeAreaInsets();
  const [userId, setUserId] = useState<string | null>(null);
  useEffect(() => {
    getOrCreateUserId().then(setUserId);
  }, []);

  const { data, isLoading } = useQuery({
    queryKey: ["bookings", userId],
    queryFn: () => fetchUserBookings(userId!),
    enabled: Boolean(userId),
    refetchOnMount: "always",
  });

  if (!userId || isLoading) {
    return (
      <View
        className="flex-1 bg-paper-100 items-center justify-center"
        style={{ paddingTop: insets.top }}
      >
        <Text className="text-ink-200 text-sm">Loading bookings…</Text>
      </View>
    );
  }

  const upcoming = data?.upcoming ?? [];
  const past = data?.past ?? [];

  if (upcoming.length === 0 && past.length === 0) {
    return <EmptyState insets={insets} />;
  }

  const rows: Row[] = [];
  if (upcoming.length > 0) {
    rows.push({ kind: "header", label: "Upcoming" });
    for (const b of upcoming) rows.push({ kind: "booking", booking: b });
  }
  if (past.length > 0) {
    rows.push({ kind: "header", label: "Past" });
    for (const b of past) rows.push({ kind: "booking", booking: b });
  }

  return (
    <View className="flex-1 bg-paper-100" style={{ paddingTop: insets.top + 12 }}>
      <Text className="text-ink-800 text-2xl font-semibold px-4 pb-3">Bookings</Text>
      <FlashList
        data={rows}
        keyExtractor={(r, i) =>
          r.kind === "header" ? `h-${r.label}` : `b-${r.booking.booking_id}-${i}`
        }
        getItemType={(r) => r.kind}
        renderItem={({ item }) =>
          item.kind === "header" ? (
            <Text className="text-ink-500 text-xs uppercase tracking-wider px-4 pt-4 pb-2">
              {item.label}
            </Text>
          ) : (
            <BookingRow booking={item.booking} />
          )
        }
        contentContainerStyle={{ paddingBottom: 32 }}
      />
    </View>
  );
}

function BookingRow({ booking }: { booking: BookingSummary }) {
  return (
    <Pressable
      onPress={() =>
        router.push({
          pathname: "/venue/[placeId]/book/confirm",
          params: { placeId: booking.place_id, booking_id: booking.booking_id },
        })
      }
      className="flex-row items-center bg-white mx-4 my-1 px-4 py-3 rounded-2xl border border-paper-500/60"
    >
      <View className="flex-1">
        <Text className="text-ink-800 text-sm font-semibold" numberOfLines={1}>
          {booking.venue_name}
        </Text>
        <Text className="text-ink-200 text-xs mt-0.5">
          {booking.date} · {booking.slot} · {booking.services.length}{" "}
          {booking.services.length === 1 ? "service" : "services"}
        </Text>
      </View>
      <Text className="text-ink-700 text-sm font-semibold mr-2">
        {priceLabel(booking.total_cents)}
      </Text>
      <ChevronRight size={16} color="#9A968C" />
    </Pressable>
  );
}

function EmptyState({ insets }: { insets: ReturnType<typeof useSafeAreaInsets> }) {
  return (
    <View
      className="flex-1 bg-paper-100 items-center justify-center px-8"
      style={{ paddingTop: insets.top }}
    >
      <Calendar size={36} color="#9A968C" />
      <Text className="text-ink-800 text-lg font-semibold mt-3">No bookings yet</Text>
      <Text className="text-ink-200 text-sm text-center mt-2">
        Find something to book — your reservations will show up here.
      </Text>
      <Pressable
        onPress={() => router.push("/(tabs)")}
        className="mt-6 px-4 py-3 bg-ink-800 rounded-2xl"
      >
        <Text className="text-paper-100 text-sm font-semibold">Find something to book</Text>
      </Pressable>
    </View>
  );
}
