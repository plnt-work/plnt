// Slot grid for the Time step. Fetches /availability via react-query,
// keyed on (placeId, date, serviceIds, proId) so chips refresh when
// any input changes.
import { Pressable, Text, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { fetchAvailability, type Slot } from "@/lib/api/venues";

const BRAND_VIOLET = "#A672E0";

interface Props {
  placeId: string;
  date: string;
  serviceIds: string[];
  proId: string;
  selectedSlot: string | null;
  onPickSlot: (slot: Slot) => void;
}

export function SlotList({
  placeId,
  date,
  serviceIds,
  proId,
  selectedSlot,
  onPickSlot,
}: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["availability", placeId, date, [...serviceIds].sort().join(","), proId],
    queryFn: () => fetchAvailability(placeId, date, serviceIds, proId),
  });

  if (isLoading) {
    return <Text className="text-ink-200 text-sm px-4 mt-4">Loading times…</Text>;
  }
  if (isError) {
    return <Text className="text-rust-500 text-sm px-4 mt-4">Couldn’t load times.</Text>;
  }
  if (!data || data.slots.length === 0) {
    return <Text className="text-ink-200 text-sm px-4 mt-4">No availability that day.</Text>;
  }

  return (
    <View className="flex-row flex-wrap px-4 mt-2">
      {data.slots.map((s) => {
        const active = s === selectedSlot;
        return (
          <Pressable
            key={s}
            onPress={() => onPickSlot(s)}
            style={{
              backgroundColor: active ? BRAND_VIOLET : "#FBF7EE",
              borderColor: active ? BRAND_VIOLET : "#E4DCC6",
              borderWidth: 1,
            }}
            className="px-3 py-2 rounded-xl mr-2 mb-2"
          >
            <Text
              className={
                "text-sm font-medium " + (active ? "text-white" : "text-ink-800")
              }
            >
              {s}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}
