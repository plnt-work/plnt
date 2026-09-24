// Confirm step — summary card, Pay-in-store (locked), Confirm CTA.
// Doubles as the read-only booking view when invoked with ?booking_id=X
// (the assistant sheet and the Bookings tab both link in this way).
import { useEffect, useMemo, useState } from "react";
import { Alert, Pressable, ScrollView, Text, View } from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { Check, MapPin, Lock } from "lucide-react-native";

import { useCart, totalCents, totalMinutes } from "@/features/booking/cart";
import { createBooking, fetchBooking, type BookingSummary } from "@/lib/api/bookings";
import { getOrCreateUserId } from "@/lib/storage/identity";
import { SAMPLE_BUSINESSES } from "@web/places/sample-businesses";

const BRAND_VIOLET = "#A672E0";

function priceLabel(cents: number): string {
  return `₹${(cents / 100).toFixed(0)}`;
}

export default function ConfirmStep() {
  const { placeId, booking_id } = useLocalSearchParams<{
    placeId: string;
    booking_id?: string;
  }>();

  const business = useMemo(
    () => SAMPLE_BUSINESSES.find((b) => b.place_id === placeId) ?? null,
    [placeId],
  );

  // Read-only mode when a booking_id is supplied.
  if (booking_id) {
    return <ReadOnly bookingId={booking_id} venueName={business?.display_name ?? "Venue"} />;
  }
  return <EditableConfirm placeId={placeId!} venueName={business?.display_name ?? "Venue"} />;
}

// ─────────────────────────── editable (default) ───────────────────────────

function EditableConfirm({ placeId, venueName }: { placeId: string; venueName: string }) {
  const services = useCart((s) => s.services);
  const proId = useCart((s) => s.proId);
  const slot = useCart((s) => s.slot);
  const date = useCart((s) => s.date);
  const reset = useCart((s) => s.reset);
  const [userId, setUserId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getOrCreateUserId().then(setUserId);
  }, []);

  const ready = services.length > 0 && proId !== null && slot !== null && date !== null;

  const onConfirm = async () => {
    if (!ready || !userId) return;
    setSubmitting(true);
    try {
      const booking = await createBooking(
        {
          place_id: placeId,
          venue_name: venueName,
          user_id: userId,
          date: date!,
          slot: slot!,
          pro_id: String(proId),
          service_ids: services.map((s) => s.id),
        },
        { services, venue_name: venueName },
      );
      reset();
      router.replace({
        pathname: "/venue/[placeId]/book/confirm",
        params: { placeId, booking_id: booking.booking_id },
      });
    } catch (e) {
      Alert.alert("Couldn’t confirm booking", String((e as Error).message ?? e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ScrollView className="flex-1 bg-paper-100" contentContainerStyle={{ paddingBottom: 32 }}>
      <SummaryCard
        venueName={venueName}
        date={date}
        slot={slot}
        services={services}
        proId={String(proId ?? "no-preference")}
      />

      <PaymentSection />

      <View className="px-4 mt-4">
        <Pressable
          onPress={onConfirm}
          disabled={!ready || submitting || !userId}
          className={
            "rounded-2xl py-4 items-center " +
            (!ready || submitting || !userId ? "bg-paper-500" : "bg-ink-800")
          }
        >
          <Text
            className={
              "font-semibold text-base " +
              (!ready || submitting ? "text-ink-200" : "text-paper-100")
            }
          >
            {submitting ? "Confirming…" : "Confirm booking"}
          </Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

// ─────────────────────────── read-only ───────────────────────────

function ReadOnly({ bookingId, venueName }: { bookingId: string; venueName: string }) {
  const [userId, setUserId] = useState<string | null>(null);
  useEffect(() => {
    getOrCreateUserId().then(setUserId);
  }, []);

  const { data, isLoading } = useQuery({
    queryKey: ["booking", userId, bookingId],
    queryFn: () => fetchBooking(userId!, bookingId),
    enabled: Boolean(userId),
  });

  if (isLoading || !data) {
    return (
      <View className="flex-1 items-center justify-center bg-paper-100">
        <Text className="text-ink-200 text-sm">Loading booking…</Text>
      </View>
    );
  }

  return (
    <ScrollView className="flex-1 bg-paper-100" contentContainerStyle={{ paddingBottom: 32 }}>
      <View
        className="mx-4 mt-4 bg-white rounded-2xl p-4"
        style={{ borderColor: BRAND_VIOLET, borderWidth: 1 }}
      >
        <View className="flex-row items-center gap-2 mb-2">
          <Check size={16} color={BRAND_VIOLET} />
          <Text className="text-ink-800 text-sm font-semibold">Confirmed</Text>
        </View>
        <Text className="text-ink-200 text-xs">Booking id</Text>
        <Text selectable className="text-ink-800 text-xs font-mono">{data.booking_id}</Text>
      </View>

      <SummaryCard
        venueName={data.venue_name || venueName}
        date={data.date}
        slot={data.slot}
        services={data.services}
        proId={data.pro_id}
      />

      <PaymentSection />
    </ScrollView>
  );
}

// ─────────────────────────── shared ───────────────────────────

function SummaryCard({
  venueName,
  date,
  slot,
  services,
  proId,
}: {
  venueName: string;
  date: string | null;
  slot: string | null;
  services: BookingSummary["services"];
  proId: string;
}) {
  return (
    <View className="mx-4 mt-4 bg-white rounded-2xl p-4 border border-paper-500/60">
      <View className="flex-row items-center gap-2 mb-3">
        <MapPin size={16} color="#3A3A36" />
        <Text className="text-ink-800 text-base font-semibold flex-1" numberOfLines={1}>
          {venueName}
        </Text>
      </View>
      <Text className="text-ink-200 text-xs uppercase tracking-wider">Date · Time</Text>
      <Text className="text-ink-800 text-sm mt-1">
        {date || "—"} · {slot || "—"}
      </Text>
      <Text className="text-ink-200 text-xs uppercase tracking-wider mt-3">Professional</Text>
      <Text className="text-ink-800 text-sm mt-1">
        {proId === "no-preference" ? "No preference" : proId}
      </Text>
      <Text className="text-ink-200 text-xs uppercase tracking-wider mt-3">Services</Text>
      {services.map((s) => (
        <View key={s.id} className="flex-row items-center justify-between mt-2">
          <Text className="text-ink-800 text-sm flex-1 pr-4">{s.name}</Text>
          <Text className="text-ink-700 text-sm font-medium">{priceLabel(s.price_cents)}</Text>
        </View>
      ))}
      <View className="border-t border-paper-500/60 mt-3 pt-3 flex-row items-center justify-between">
        <Text className="text-ink-800 text-sm font-semibold">Total</Text>
        <View className="items-end">
          <Text className="text-ink-800 text-base font-semibold">
            {priceLabel(totalCents({ services }))}
          </Text>
          <Text className="text-ink-200 text-xs">{totalMinutes({ services })} min</Text>
        </View>
      </View>
    </View>
  );
}

function PaymentSection() {
  return (
    <View className="mx-4 mt-4 bg-white rounded-2xl p-4 border border-paper-500/60">
      <Text className="text-ink-200 text-xs uppercase tracking-wider mb-2">Payment</Text>
      <View className="flex-row items-center gap-2">
        <View
          style={{
            width: 18,
            height: 18,
            borderRadius: 999,
            borderWidth: 2,
            borderColor: BRAND_VIOLET,
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <View style={{ width: 8, height: 8, borderRadius: 999, backgroundColor: BRAND_VIOLET }} />
        </View>
        <Text className="text-ink-800 text-sm font-medium flex-1">Pay in store</Text>
        <Lock size={14} color="#9A968C" />
      </View>
      <Text className="text-ink-200 text-xs mt-2">
        Online payment isn’t available yet — settle at the venue.
      </Text>
    </View>
  );
}
