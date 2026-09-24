// Time step — date strip + slot grid. Selecting a slot writes both
// date + slot into the cart; the CartSummary advances to /confirm.
import { useState } from "react";
import { View } from "react-native";
import { useLocalSearchParams, router } from "expo-router";

import { DateStrip } from "@/features/booking/DateStrip";
import { SlotList } from "@/features/booking/SlotList";
import { CartSummary } from "@/features/booking/CartSummary";
import { useCart } from "@/features/booking/cart";
import { ymd } from "@/features/booking/date-strip-util";

export default function TimeStep() {
  const { placeId } = useLocalSearchParams<{ placeId: string }>();
  const services = useCart((s) => s.services);
  const proId = useCart((s) => s.proId);
  const slot = useCart((s) => s.slot);
  const date = useCart((s) => s.date);
  const setSlot = useCart((s) => s.setSlot);

  // Default the date strip to today; user can pick any of the 7 cells.
  const [pickedDate, setPickedDate] = useState<string>(date ?? ymd(new Date()));

  return (
    <View className="flex-1 bg-paper-100">
      <DateStrip selectedDate={pickedDate} onPick={setPickedDate} />
      <SlotList
        placeId={placeId!}
        date={pickedDate}
        serviceIds={services.map((s) => s.id)}
        proId={String(proId ?? "no-preference")}
        selectedSlot={pickedDate === date ? slot : null}
        onPickSlot={(s) => setSlot(pickedDate, s)}
      />
      <CartSummary
        ctaLabel="Continue"
        ctaDisabled={!slot || !date}
        onPress={() =>
          router.push({ pathname: "/venue/[placeId]/book/confirm", params: { placeId: placeId! } })
        }
      />
    </View>
  );
}
