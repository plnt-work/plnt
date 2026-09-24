import { Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { fetchTeam } from "@/lib/api/venues";

interface Props {
  placeId: string;
}

export function TeamGrid({ placeId }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ["team", placeId],
    queryFn: () => fetchTeam(placeId),
  });

  return (
    <View className="px-4 pt-6">
      <Text className="text-ink-800 text-lg font-semibold mb-2">Team</Text>
      {isLoading ? <Text className="text-ink-200 text-sm">Loading…</Text> : null}
      <View className="flex-row flex-wrap -mx-1">
        {data?.map((m) => (
          <View key={m.id} className="w-1/3 px-1 mb-3 items-center">
            <View className="w-16 h-16 rounded-full bg-paper-300 items-center justify-center">
              <Text className="text-ink-700 font-semibold text-lg">
                {m.name.split(" ").map((p) => p[0]).join("").slice(0, 2)}
              </Text>
            </View>
            <Text className="text-ink-800 text-xs font-medium mt-2" numberOfLines={1}>
              {m.name}
            </Text>
            <Text className="text-ink-200 text-xs" numberOfLines={1}>
              {m.role}
            </Text>
          </View>
        ))}
      </View>
    </View>
  );
}
