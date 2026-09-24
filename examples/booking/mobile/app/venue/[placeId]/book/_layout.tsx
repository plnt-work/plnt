// Booking stack — child of the venue/[placeId] route. Headers come
// from BookingHeader, scoped per route via screenOptions's header prop.
import { Stack } from "expo-router";
import { BookingHeader } from "@/features/booking/BookingHeader";

export default function BookLayout() {
  return (
    <Stack>
      <Stack.Screen
        name="services"
        options={{ header: () => <BookingHeader step="services" /> }}
      />
      <Stack.Screen
        name="professional"
        options={{ header: () => <BookingHeader step="professional" /> }}
      />
      <Stack.Screen
        name="time"
        options={{ header: () => <BookingHeader step="time" /> }}
      />
      <Stack.Screen
        name="confirm"
        options={{ header: () => <BookingHeader step="confirm" /> }}
      />
    </Stack>
  );
}
