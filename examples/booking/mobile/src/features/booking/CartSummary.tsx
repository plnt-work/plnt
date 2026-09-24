// Sticky bottom summary card. Always shows total + duration + a primary
// CTA. Hides itself when cart is empty (services step entry).
import { Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useCart, totalCents, totalMinutes } from "./cart";

interface Props {
  ctaLabel: string;
  ctaDisabled?: boolean;
  onPress: () => void;
}

function priceLabel(cents: number): string {
  return `₹${(cents / 100).toFixed(0)}`;
}

export function CartSummary({ ctaLabel, ctaDisabled = false, onPress }: Props) {
  const insets = useSafeAreaInsets();
  const services = useCart((s) => s.services);
  if (services.length === 0) return null;

  return (
    <View
      className="bg-white border-t border-paper-500/60 px-4 pt-3"
      style={{ paddingBottom: insets.bottom + 12 }}
    >
      <View className="flex-row items-center justify-between mb-2">
        <View>
          <Text className="text-ink-800 text-base font-semibold">
            {priceLabel(totalCents({ services }))}
          </Text>
          <Text className="text-ink-200 text-xs">
            {services.length} {services.length === 1 ? "service" : "services"} ·{" "}
            {totalMinutes({ services })} min
          </Text>
        </View>
      </View>
      <Pressable
        onPress={onPress}
        disabled={ctaDisabled}
        className={
          "rounded-2xl py-3 items-center " + (ctaDisabled ? "bg-paper-500" : "bg-ink-800")
        }
      >
        <Text
          className={
            "font-semibold text-sm " + (ctaDisabled ? "text-ink-200" : "text-paper-100")
          }
        >
          {ctaLabel}
        </Text>
      </Pressable>
    </View>
  );
}
