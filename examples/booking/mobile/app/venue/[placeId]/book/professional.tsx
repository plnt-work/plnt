// Professional step — single-select. "No preference" is the first row
// and persists as the literal string "no-preference" in the cart.
import { Pressable, Text, View } from "react-native";
import { FlashList } from "@shopify/flash-list";
import { useLocalSearchParams, router } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { Check, User } from "lucide-react-native";

import { fetchTeam, type TeamMember } from "@/lib/api/venues";
import { useCart, type ProSelection } from "@/features/booking/cart";
import { CartSummary } from "@/features/booking/CartSummary";

type Row = { id: ProSelection; name: string; role: string };

export default function ProfessionalStep() {
  const { placeId } = useLocalSearchParams<{ placeId: string }>();
  const proId = useCart((s) => s.proId);
  const setPro = useCart((s) => s.setPro);

  const { data, isLoading } = useQuery({
    queryKey: ["team", placeId],
    queryFn: () => fetchTeam(placeId!),
    enabled: Boolean(placeId),
  });

  const rows: Row[] = [
    { id: "no-preference", name: "No preference", role: "Any available" },
    ...((data ?? []).map((m: TeamMember) => ({
      id: m.id,
      name: m.name,
      role: m.role,
    })) as Row[]),
  ];

  const renderItem = ({ item }: { item: Row }) => {
    const active = proId === item.id;
    return (
      <Pressable
        onPress={() => setPro(item.id)}
        className="flex-row items-center justify-between py-4 px-4 border-b border-paper-500/40"
      >
        <View className="flex-row items-center flex-1">
          <View className="w-10 h-10 rounded-full bg-paper-200 items-center justify-center mr-3">
            <User size={18} color="#3A3A36" />
          </View>
          <View className="flex-1">
            <Text className="text-ink-800 text-sm font-medium">{item.name}</Text>
            <Text className="text-ink-200 text-xs mt-0.5">{item.role}</Text>
          </View>
        </View>
        {active ? (
          <View className="w-6 h-6 rounded-full bg-ink-800 items-center justify-center">
            <Check size={14} color="#FBF7EE" />
          </View>
        ) : (
          <View className="w-6 h-6 rounded-full border border-paper-600" />
        )}
      </Pressable>
    );
  };

  return (
    <View className="flex-1 bg-paper-100">
      {isLoading ? (
        <Text className="text-ink-200 text-sm px-4 pt-4">Loading…</Text>
      ) : (
        <FlashList
          data={rows}
          keyExtractor={(r) => String(r.id)}
          renderItem={renderItem}
          extraData={proId}
          contentContainerStyle={{ paddingBottom: 16 }}
        />
      )}
      <CartSummary
        ctaLabel="Continue"
        ctaDisabled={proId === null}
        onPress={() =>
          router.push({ pathname: "/venue/[placeId]/book/time", params: { placeId: placeId! } })
        }
      />
    </View>
  );
}
