// Tab navigator — Home / Bookings / Profile. Explore was folded into
// Home (Fresha-style map screen) so the tab bar drops to three.
// Active tint = brand-violet (tokens.colors.iri.violet).
import { Tabs } from "expo-router";
import { Home, CalendarCheck, User } from "lucide-react-native";
import tokens from "@/styles/tokens";

const BRAND_VIOLET = tokens.colors.iri.violet;

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: BRAND_VIOLET,
        tabBarInactiveTintColor: "#9A968C",
        tabBarStyle: { backgroundColor: "#FBF7EE", borderTopColor: "#E4DCC6" },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Home",
          tabBarIcon: ({ color, size }) => <Home color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="bookings"
        options={{
          title: "Bookings",
          tabBarIcon: ({ color, size }) => <CalendarCheck color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ color, size }) => <User color={color} size={size} />,
        }}
      />
    </Tabs>
  );
}
