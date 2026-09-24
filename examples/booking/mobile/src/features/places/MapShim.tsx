// Native MapShim — re-exports react-native-maps directly. The `.web.tsx`
// sibling renders a placeholder so the web bundle doesn't pull in the
// native module (it has no JS web build).
export { default } from "react-native-maps";
export { Marker, PROVIDER_GOOGLE } from "react-native-maps";
export type { Region } from "react-native-maps";
