import { Linking, Pressable, Text, View } from "react-native";
import { Clock, Phone, Globe, MapPin } from "lucide-react-native";
import type { Business } from "@web/places/types";

interface Props {
  business: Business;
}

function Row({ icon, label, onPress }: { icon: React.ReactNode; label: string; onPress?: () => void }) {
  const inner = (
    <View className="flex-row items-center gap-3 py-2">
      <View className="w-5">{icon}</View>
      <Text className="text-ink-700 text-sm flex-1">{label}</Text>
    </View>
  );
  return onPress ? <Pressable onPress={onPress}>{inner}</Pressable> : inner;
}

export function AboutSection({ business }: Props) {
  return (
    <View className="px-4 pt-4">
      <Text className="text-ink-800 text-2xl font-semibold">
        {business.display_name}
      </Text>
      <Text className="text-ink-500 text-sm mt-1">
        ★ {business.rating.toFixed(1)} · {business.user_ratings.toLocaleString()} reviews
      </Text>
      <View className="mt-3 border-t border-paper-500/60">
        <Row icon={<MapPin size={16} color="#3A3A36" />} label={business.address} />
        {business.hours ? (
          <Row icon={<Clock size={16} color="#3A3A36" />} label={business.hours} />
        ) : null}
        {business.phone ? (
          <Row
            icon={<Phone size={16} color="#3A3A36" />}
            label={business.phone}
            onPress={() => Linking.openURL(`tel:${business.phone}`)}
          />
        ) : null}
        {business.web ? (
          <Row
            icon={<Globe size={16} color="#3A3A36" />}
            label={business.web}
            onPress={() => Linking.openURL(business.web!)}
          />
        ) : null}
      </View>
    </View>
  );
}
