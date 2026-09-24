import { Text, View } from "react-native";
import { Star } from "lucide-react-native";
import { useQuery } from "@tanstack/react-query";
import { fetchReviews } from "@/lib/api/venues";

interface Props {
  placeId: string;
}

export function ReviewsList({ placeId }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ["reviews", placeId],
    queryFn: () => fetchReviews(placeId),
  });

  return (
    <View className="px-4 pt-6 pb-12">
      <Text className="text-ink-800 text-lg font-semibold mb-2">Reviews</Text>
      {isLoading ? <Text className="text-ink-200 text-sm">Loading…</Text> : null}
      {data?.map((r) => (
        <View key={r.id} className="py-3 border-b border-paper-500/40">
          <View className="flex-row items-center justify-between">
            <Text className="text-ink-800 text-sm font-medium">{r.author}</Text>
            <View className="flex-row items-center gap-1">
              <Star size={12} color="#C97B2A" fill="#C97B2A" />
              <Text className="text-ink-700 text-xs">{r.rating.toFixed(1)}</Text>
            </View>
          </View>
          <Text className="text-ink-500 text-sm mt-1">{r.text}</Text>
          <Text className="text-ink-200 text-xs mt-1">{r.at}</Text>
        </View>
      ))}
    </View>
  );
}
