// Horizontal 7-day picker. Today is highlighted in brand-violet when
// selected; other days are inert chip-style buttons.
import { Pressable, ScrollView, Text, View } from "react-native";
import { buildDateStrip } from "./date-strip-util";

const BRAND_VIOLET = "#A672E0";

interface Props {
  selectedDate: string | null;
  onPick: (date: string) => void;
  today?: Date;
}

export function DateStrip({ selectedDate, onPick, today = new Date() }: Props) {
  const cells = buildDateStrip(today);
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={{ paddingHorizontal: 16, paddingVertical: 12 }}
    >
      {cells.map((c) => {
        const active = c.date === selectedDate;
        return (
          <Pressable
            key={c.date}
            onPress={() => onPick(c.date)}
            style={{
              backgroundColor: active ? BRAND_VIOLET : "#FBF7EE",
              borderColor: active ? BRAND_VIOLET : "#E4DCC6",
              borderWidth: 1,
            }}
            className="w-14 h-16 mr-2 rounded-2xl items-center justify-center"
          >
            <Text
              className={
                "text-xs " + (active ? "text-white/90" : "text-ink-200")
              }
            >
              {c.dow}
            </Text>
            <Text
              className={
                "text-lg font-semibold " + (active ? "text-white" : "text-ink-800")
              }
            >
              {c.dom}
            </Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}
