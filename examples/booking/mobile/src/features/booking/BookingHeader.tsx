// Progress header for the booking stack — Services > Professional >
// Time > Confirm. Rendered as a custom Stack screenOptions.header.
import { Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { router } from "expo-router";
import { ChevronLeft } from "lucide-react-native";

import type { BookingStep } from "./cart";

const ORDER: BookingStep[] = ["services", "professional", "time", "confirm"];
const LABEL: Record<BookingStep, string> = {
  services: "Services",
  professional: "Professional",
  time: "Time",
  confirm: "Confirm",
};

const BRAND_VIOLET = "#A672E0";

interface Props {
  step: BookingStep;
}

export function BookingHeader({ step }: Props) {
  const insets = useSafeAreaInsets();
  const currentIndex = ORDER.indexOf(step);

  return (
    <View
      className="bg-white border-b border-paper-500/60"
      style={{ paddingTop: insets.top + 4 }}
    >
      <View className="flex-row items-center px-2 py-2">
        <Pressable
          onPress={() => router.back()}
          accessibilityRole="button"
          accessibilityLabel="Back"
          className="w-10 h-10 items-center justify-center"
        >
          <ChevronLeft size={22} color="#0E1116" />
        </Pressable>
        <View className="flex-1 flex-row items-center justify-center pr-10">
          {ORDER.map((s, i) => {
            const active = i === currentIndex;
            const done = i < currentIndex;
            return (
              <View key={s} className="flex-row items-center">
                <View
                  style={{
                    backgroundColor: active || done ? BRAND_VIOLET : "#E4DCC6",
                    width: 18,
                    height: 18,
                    borderRadius: 999,
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Text className="text-[10px] text-white font-semibold">{i + 1}</Text>
                </View>
                {i < ORDER.length - 1 ? (
                  <View
                    style={{
                      width: 16,
                      height: 2,
                      backgroundColor: done ? BRAND_VIOLET : "#E4DCC6",
                      marginHorizontal: 4,
                    }}
                  />
                ) : null}
              </View>
            );
          })}
        </View>
      </View>
      <Text className="text-ink-800 text-base font-semibold text-center pb-2">
        {LABEL[step]}
      </Text>
    </View>
  );
}
