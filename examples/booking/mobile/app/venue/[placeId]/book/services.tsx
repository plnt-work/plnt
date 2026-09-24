// Services step — multi-select list of services with cart-toggle taps.
// Sticky bottom CartSummary advances to /professional when cart > 0.
import { useEffect } from "react";
import { Pressable, Text, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useLocalSearchParams, router } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { Check, Plus } from "lucide-react-native";

import { fetchServices, type Service } from "@/lib/api/venues";
import { useCart } from "@/features/booking/cart";
import { CartSummary } from "@/features/booking/CartSummary";

function priceLabel(cents: number): string {
  return `₹${(cents / 100).toFixed(0)}`;
}

export default function ServicesStep() {
  const { placeId } = useLocalSearchParams<{ placeId: string }>();
  const setPlace = useCart((s) => s.setPlace);
  const services = useCart((s) => s.services);
  const toggleService = useCart((s) => s.toggleService);

  // Bind the cart to this venue on entry — also wipes a stale cart if
  // the user switched venues mid-flow.
  useEffect(() => {
    if (placeId) setPlace(placeId);
  }, [placeId, setPlace]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["services", placeId],
    queryFn: () => fetchServices(placeId!),
    enabled: Boolean(placeId),
  });

  const isPicked = (id: string) => services.some((s) => s.id === id);

  const renderItem = ({ item }: { item: Service }) => {
    const picked = isPicked(item.id);
    return (
      <Pressable
        onPress={() => toggleService(item)}
        className="flex-row items-center justify-between py-4 px-4 border-b border-paper-500/40"
      >
        <View className="flex-1 pr-4">
          <Text className="text-ink-800 text-sm font-medium">{item.name}</Text>
          <Text className="text-ink-200 text-xs mt-0.5">
            {item.duration_min} min · {priceLabel(item.price_cents)}
          </Text>
        </View>
        <View
          className={
            "w-8 h-8 items-center justify-center rounded-full " +
            (picked ? "bg-ink-800" : "bg-paper-200")
          }
        >
          {picked ? (
            <Check size={16} color="#FBF7EE" />
          ) : (
            <Plus size={16} color="#3A3A36" />
          )}
        </View>
      </Pressable>
    );
  };

  return (
    <View className="flex-1 bg-paper-100">
      {isLoading ? (
        <Text className="text-ink-200 text-sm px-4 pt-4">Loading…</Text>
      ) : isError ? (
        <Text className="text-rust-500 text-sm px-4 pt-4">Couldn’t load services.</Text>
      ) : (
        <FlashList
          data={data ?? []}
          keyExtractor={(s) => s.id}
          renderItem={renderItem}
          extraData={services}
          contentContainerStyle={{ paddingBottom: 16 }}
        />
      )}
      <CartSummary
        ctaLabel="Continue"
        onPress={() => router.push({ pathname: "/venue/[placeId]/book/professional", params: { placeId: placeId! } })}
      />
    </View>
  );
}
