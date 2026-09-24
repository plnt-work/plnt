// Web MapShim — react-native-maps has no web build. We render a
// labeled placeholder so the rest of the screen (search pill, sheet,
// chips, list, navigation) is exercisable in a browser. Markers are
// silent no-ops on web — selection still flows through the parent state.
import { forwardRef, type ReactNode } from "react";
import { Text, View, type ViewStyle } from "react-native";

export interface Region {
  latitude: number;
  longitude: number;
  latitudeDelta: number;
  longitudeDelta: number;
}

export interface MapViewHandle {
  animateToRegion(_r: Region, _ms?: number): void;
}

// Loose typing — the call site passes ~10 native-only props (provider,
// showsUserLocation, toolbarEnabled, …) that have no web meaning. We
// accept-and-ignore the rest, but narrow `style` and `children` to
// keep tsc happy at the JSX boundary.
type MapViewProps = Record<string, unknown> & {
  style?: ViewStyle | ViewStyle[];
  initialRegion?: Region;
  children?: ReactNode;
};

const MapView = forwardRef<MapViewHandle, MapViewProps>(function MapView(props, ref) {
  if (ref && typeof ref === "object") {
    (ref as { current: MapViewHandle | null }).current = { animateToRegion() {} };
  }
  return (
    <View style={[{ flex: 1, backgroundColor: "#E4DCC6", alignItems: "center", justifyContent: "center" }, props.style as ViewStyle]}>
      <View style={{ paddingHorizontal: 24, paddingVertical: 12, backgroundColor: "#FBF7EE", borderRadius: 16 }}>
        <Text style={{ color: "#3A3A36", fontSize: 13, fontWeight: "600" }}>
          Map unavailable on web
        </Text>
        <Text style={{ color: "#6C6A60", fontSize: 11, marginTop: 4 }}>
          react-native-maps is native-only. The sheet, chips, and list still work.
        </Text>
      </View>
      {props.children as ReactNode}
    </View>
  );
});

interface MarkerProps {
  coordinate: { latitude: number; longitude: number };
  onPress?: () => void;
  children?: ReactNode;
  [key: string]: unknown;
}

// Markers render nothing on web — taps would normally select a venue,
// but with no map there's no place to put them. Selection still works
// from the sheet's card list.
function Marker(_props: MarkerProps) {
  return null;
}

const PROVIDER_GOOGLE = "google";

export default MapView;
export { Marker, PROVIDER_GOOGLE };
