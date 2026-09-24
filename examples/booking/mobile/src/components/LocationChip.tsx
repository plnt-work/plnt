// Top-left location pill on Home. Shows current locality (or a stub
// "Locating…") and acts as the affordance to re-request permission.
import { Pressable, Text, View } from "react-native";
import { MapPin } from "lucide-react-native";

interface Props {
  label: string;
  onPress?: () => void;
}

export function LocationChip({ label, onPress }: Props) {
  return (
    <Pressable
      onPress={onPress}
      className="flex-row items-center gap-2 px-3 py-2 bg-paper-200 rounded-full self-start"
    >
      <View className="w-4 h-4 items-center justify-center">
        <MapPin size={14} color="#3A3A36" />
      </View>
      <Text className="text-ink-700 text-sm font-medium">{label}</Text>
    </Pressable>
  );
}
