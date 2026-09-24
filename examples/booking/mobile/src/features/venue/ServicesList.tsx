import { Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { fetchServices } from "@/lib/api/venues";

interface Props {
  placeId: string;
}

function priceLabel(cents: number): string {
  return `₹${(cents / 100).toFixed(0)}`;
}

export function ServicesList({ placeId }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["services", placeId],
    queryFn: () => fetchServices(placeId),
  });

  return (
    <View className="px-4 pt-6">
      <Text className="text-ink-800 text-lg font-semibold mb-2">Services</Text>
      {isLoading ? <Text className="text-ink-200 text-sm">Loading…</Text> : null}
      {isError ? <Text className="text-rust-500 text-sm">Failed to load services.</Text> : null}
      {data?.map((s) => (
        <View
          key={s.id}
          className="flex-row items-start justify-between py-3 border-b border-paper-500/40"
        >
          <View className="flex-1 pr-4">
            <Text className="text-ink-800 text-sm font-medium">{s.name}</Text>
            <Text className="text-ink-200 text-xs mt-0.5">{s.duration_min} min</Text>
          </View>
          <Text className="text-ink-700 text-sm font-semibold">{priceLabel(s.price_cents)}</Text>
        </View>
      ))}
    </View>
  );
}
