// Home — Fresha-style search/map screen.
//
// Layout (full-bleed):
//   ┌─────────────────────────────┐
//   │ <SearchPill> (mt-safe + mx-4)│  overlay on map
//   │                             │
//   │       react-native-maps     │  full screen
//   │       custom MarkerPills    │
//   │                             │
//   │ ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔ <— handle  │
//   │ [SearchResultsBanner?]      │  sticky in sheet (agent reply)
//   │ <FilterChips>               │  sticky in sheet
//   │ X venues nearby             │
//   │ <FlashList of VenueCard>    │
//   └─────────────────────────────┘
//
// One filter object → both markers and cards; the marker↔card sync is
// kept inside this file because both sides need the same refs.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Text, View } from "react-native";
// Map import goes through MapShim so the web bundle resolves to a
// placeholder; native uses react-native-maps directly.
import MapView, { Marker, PROVIDER_GOOGLE, type Region } from "@/features/places/MapShim";
import BottomSheet, {
  BottomSheetModalProvider,
  useBottomSheetScrollableCreator,
} from "@gorhom/bottom-sheet";
import { FlashList, type FlashListRef } from "@shopify/flash-list";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import * as Location from "expo-location";

import { SearchPill } from "@/components/SearchPill";
import { FilterChips } from "@/features/places/FilterChips";
import { MarkerPill } from "@/features/places/MarkerPill";
import { VenueCard } from "@/features/places/VenueCard";
import { SearchResultsBanner } from "@/features/places/SearchResultsBanner";
import { FilterDrawer, type FilterDrawerHandle, type FilterValue } from "@/components/FilterDrawer";
import { CATEGORIES } from "@/features/places/categories";
import { filterVenues } from "@/features/places/filter";
import { useSearch, setSearch } from "@/features/search/store";
import { useHomeSearchDispatch } from "@/features/chat/useHomeSearchDispatch";

import { SAMPLE_BUSINESSES, COLABA_CENTER } from "@web/places/sample-businesses";
import type { Business } from "@web/places/types";

const INITIAL_REGION: Region = {
  latitude: COLABA_CENTER.lat,
  longitude: COLABA_CENTER.lng,
  latitudeDelta: 0.02,
  longitudeDelta: 0.02,
};

export default function HomeScreen() {
  return (
    <BottomSheetModalProvider>
      <HomeInner />
    </BottomSheetModalProvider>
  );
}

function HomeInner() {
  const insets = useSafeAreaInsets();
  const search = useSearch();

  const [activeCategory, setActiveCategory] = useState<string>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filterValue, setFilterValue] = useState<FilterValue>({
    vertical: null,
    minRating: 0,
    maxKm: 10,
  });

  const mapRef = useRef<MapView>(null);
  const listRef = useRef<FlashListRef<Business>>(null);
  const sheetRef = useRef<BottomSheet>(null);
  const drawerRef = useRef<FilterDrawerHandle>(null);

  const snapPoints = useMemo(() => ["12%", "45%", "90%"], []);

  // ─── search WS — owns the only Home dispatcher ───────────────────
  const { dispatch, banner, searchResultsPlaceIds } = useHomeSearchDispatch({
    userLoc: search.userLoc,
  });

  // /search modal writes search.query → fire the freeform turn here so
  // there is exactly one WS connection backing Home.
  const lastDispatchedRef = useRef<string | null>(null);
  useEffect(() => {
    const q = search.query;
    if (!q) {
      lastDispatchedRef.current = null;
      return;
    }
    if (lastDispatchedRef.current === q) return;
    lastDispatchedRef.current = q;
    dispatch(q);
  }, [search.query, dispatch]);

  // ─── location bootstrap ──────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== "granted") {
        if (!cancelled) setSearch({ locationLabel: "Set location" });
        return;
      }
      const pos = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
      if (cancelled) return;
      const userLoc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      const places = await Location.reverseGeocodeAsync({
        latitude: userLoc.lat,
        longitude: userLoc.lng,
      });
      const first = places[0];
      const label = first?.city || first?.subregion || first?.region || "Current location";
      if (!cancelled) {
        setSearch({ userLoc, locationLabel: label });
        mapRef.current?.animateToRegion(
          {
            latitude: userLoc.lat,
            longitude: userLoc.lng,
            latitudeDelta: 0.02,
            longitudeDelta: 0.02,
          },
          400,
        );
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // ─── unified filter ──────────────────────────────────────────────
  // Chip-row vertical + drawer-form vertical resolve to the same field;
  // chip wins because it's the foreground gesture. The query from
  // /search lands here too — and when the agent returns
  // action.kind="search_results", that place_id set replaces the
  // client-side text filter.
  const cat = CATEGORIES.find((c) => c.key === activeCategory);
  const effectiveVertical = cat?.vertical ?? filterValue.vertical;

  const filtered: Business[] = useMemo(() => {
    if (searchResultsPlaceIds) {
      // Agent-driven result set — preserve agent's order, ignore the
      // text query (already factored into the agent's choice).
      const byId = new Map(SAMPLE_BUSINESSES.map((b) => [b.place_id, b]));
      return searchResultsPlaceIds
        .map((id) => byId.get(id))
        .filter((b): b is Business => Boolean(b));
    }
    return filterVenues(SAMPLE_BUSINESSES, {
      vertical: effectiveVertical,
      query: search.query,
      minRating: filterValue.minRating || undefined,
    });
  }, [searchResultsPlaceIds, effectiveVertical, search.query, filterValue.minRating]);

  // ─── marker / card sync ──────────────────────────────────────────
  const indexOfSelected = useMemo(() => {
    if (!selectedId) return -1;
    return filtered.findIndex((b) => b.place_id === selectedId);
  }, [filtered, selectedId]);

  const onMarkerPress = useCallback(
    (id: string) => {
      setSelectedId(id);
      sheetRef.current?.snapToIndex(1);
      // Scroll runs after the sheet expands; FlashList ignores out-of-range
      // scrollToIndex calls so a chip-driven filter that removes the
      // selected venue is safely a no-op.
      requestAnimationFrame(() => {
        const idx = filtered.findIndex((b) => b.place_id === id);
        if (idx >= 0) {
          listRef.current?.scrollToIndex({ index: idx, animated: true });
        }
      });
    },
    [filtered],
  );

  // ─── filter drawer ───────────────────────────────────────────────
  const onApplyFilters = useCallback((next: FilterValue) => {
    setFilterValue(next);
    // Drawer-driven vertical wins if user picked one explicitly.
    if (next.vertical) {
      const match = CATEGORIES.find((c) => c.vertical === next.vertical);
      if (match) setActiveCategory(match.key);
    } else {
      setActiveCategory("all");
    }
  }, []);

  const onClearBanner = useCallback(() => {
    banner?.dismiss();
    setSearch({ query: null });
  }, [banner]);

  // ─── render ──────────────────────────────────────────────────────
  return (
    <View className="flex-1 bg-paper-100">
      <MapView
        ref={mapRef}
        style={{ flex: 1 }}
        provider={PROVIDER_GOOGLE}
        initialRegion={INITIAL_REGION}
        showsUserLocation
        showsMyLocationButton={false}
        toolbarEnabled={false}
      >
        {filtered.map((b) => (
          <Marker
            key={b.place_id}
            coordinate={{ latitude: b.lat, longitude: b.lng }}
            onPress={() => onMarkerPress(b.place_id)}
            tracksViewChanges={false}
          >
            <MarkerPill business={b} selected={selectedId === b.place_id} />
          </Marker>
        ))}
      </MapView>

      {/* Top overlay — search pill */}
      <View
        style={{ position: "absolute", top: insets.top + 8, left: 0, right: 0 }}
        className="px-4"
      >
        <SearchPill
          primary={search.query || "All treatments"}
          secondary={search.locationLabel}
          onOpenFilters={() => drawerRef.current?.open()}
        />
      </View>

      {/* Bottom sheet */}
      <BottomSheet
        ref={sheetRef}
        index={0}
        snapPoints={snapPoints}
        backgroundStyle={{ backgroundColor: "#FFFFFF" }}
        handleIndicatorStyle={{ backgroundColor: "#B6AE96" }}
      >
        <SheetContents
          banner={banner ? { text: banner.text, onClear: onClearBanner } : null}
          activeCategory={activeCategory}
          setActiveCategory={setActiveCategory}
          openFilters={() => drawerRef.current?.open()}
          listRef={listRef}
          filtered={filtered}
          selectedId={selectedId}
          indexOfSelected={indexOfSelected}
        />
      </BottomSheet>

      <FilterDrawer
        ref={drawerRef}
        initial={filterValue}
        onApply={onApplyFilters}
      />
    </View>
  );
}

interface SheetContentsProps {
  banner: { text: string; onClear: () => void } | null;
  activeCategory: string;
  setActiveCategory: (k: string) => void;
  openFilters: () => void;
  listRef: React.RefObject<FlashListRef<Business> | null>;
  filtered: Business[];
  selectedId: string | null;
  indexOfSelected: number;
}

// Hoisted out of HomeInner because useBottomSheetScrollableCreator
// must run inside the BottomSheet's children — it pulls drag/scroll
// context from the surrounding sheet.
function SheetContents({
  banner,
  activeCategory,
  setActiveCategory,
  openFilters,
  listRef,
  filtered,
  selectedId,
  indexOfSelected,
}: SheetContentsProps) {
  // Replaces the deprecated BottomSheetFlashList wrapper per gorhom's
  // migration guide — hand the inner ScrollView to FlashList directly.
  const renderScrollComponent = useBottomSheetScrollableCreator();

  return (
    <>
      {banner ? <SearchResultsBanner text={banner.text} onClear={banner.onClear} /> : null}
      <FilterChips
        activeKey={activeCategory}
        onPickCategory={setActiveCategory}
        onOpenFilters={openFilters}
      />
      <View className="px-4 pt-3 pb-1 bg-white">
        <Text className="text-ink-800 text-base font-semibold">
          {filtered.length} {filtered.length === 1 ? "venue" : "venues"} nearby
        </Text>
      </View>
      <FlashList
        ref={listRef}
        renderScrollComponent={renderScrollComponent}
        data={filtered}
        keyExtractor={(b) => b.place_id}
        contentContainerStyle={{ paddingHorizontal: 16, paddingBottom: 32 }}
        extraData={selectedId}
        renderItem={({ item, index }) => (
          <VenueCard
            business={item}
            variant="wide"
            highlighted={index === indexOfSelected}
          />
        )}
      />
    </>
  );
}
