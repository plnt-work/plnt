/**
 * MapSurface — the dominant left column of /atlas.
 *
 * Wraps @vis.gl/react-google-maps. One <AdvancedMarker> per visible
 * business; <Pin> is colored by vertical via features/places/verticals.ts.
 * The selected pin gets a soft 24px CSS accent ring layered behind it
 * inside the marker DOM so the highlight tracks with map pans/zooms.
 *
 * Default Google Maps look is preserved (no disableDefaultUI, no paper
 * restyle). The `mapId` is read from VITE_GOOGLE_MAPS_VECTOR_MAP_ID with a
 * harmless fallback — without it AdvancedMarker degrades silently and the
 * map still renders.
 *
 * When VITE_GOOGLE_MAPS_KEY is unset we render a static fallback panel so
 * the page doesn't blow up in dev without the secret.
 */
import { useCallback, useEffect } from "react";
import {
  APIProvider,
  Map,
  AdvancedMarker,
  Pin,
  useMap,
} from "@vis.gl/react-google-maps";

import type { Business } from "./types";
import { metaFor } from "./verticals";
import { COLABA_CENTER } from "./sample-businesses";

const MAPS_KEY = import.meta.env.VITE_GOOGLE_MAPS_KEY as string | undefined;
const MAP_ID =
  (import.meta.env.VITE_GOOGLE_MAPS_VECTOR_MAP_ID as string | undefined) ||
  "atlas-vector"; // fallback; AdvancedMarker auto-disables if invalid

interface Props {
  businesses: Business[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  userLoc?: { lat: number; lng: number } | null;
  /** Optional set of place_ids to render with a stronger accent ring.
   *  Used by SearchResultBanner to surface the agent's matches on the map. */
  highlightedPlaceIds?: Set<string>;
}

export default function MapSurface(props: Props) {
  if (!MAPS_KEY) return <MapFallback />;

  return (
    <APIProvider apiKey={MAPS_KEY} libraries={["marker"]}>
      <Map
        defaultCenter={COLABA_CENTER}
        defaultZoom={15}
        mapId={MAP_ID}
        gestureHandling="greedy"
        clickableIcons={false}
        // Default UI preserved per CLAUDE.md
        className="size-full"
      >
        <MapBody {...props} />
      </Map>
    </APIProvider>
  );
}

function MapBody({ businesses, selectedId, onSelect, userLoc, highlightedPlaceIds }: Props) {
  const map = useMap();

  const fitToBusinesses = useCallback(() => {
    if (!map || businesses.length === 0) return;
    const bounds = new google.maps.LatLngBounds();
    for (const b of businesses) bounds.extend({ lat: b.lat, lng: b.lng });
    if (userLoc) bounds.extend(userLoc);
    map.fitBounds(bounds, 64);
  }, [map, businesses, userLoc]);

  // Re-fit whenever the filtered set shrinks/grows so chip changes land
  // visibly. Skip when a business is already selected — panning out from
  // under the user mid-conversation is jarring.
  useEffect(() => {
    if (selectedId) return;
    fitToBusinesses();
  }, [businesses.length, selectedId, fitToBusinesses]);

  // Pan to the selected pin without changing zoom.
  useEffect(() => {
    if (!map || !selectedId) return;
    const sel = businesses.find((b) => b.place_id === selectedId);
    if (sel) map.panTo({ lat: sel.lat, lng: sel.lng });
  }, [map, selectedId, businesses]);

  return (
    <>
      {businesses.map((b) => {
        const meta = metaFor(b.vertical);
        const isSelected = b.place_id === selectedId;
        const isHighlighted = !isSelected && !!highlightedPlaceIds?.has(b.place_id);
        return (
          <AdvancedMarker
            key={b.place_id}
            position={{ lat: b.lat, lng: b.lng }}
            title={b.display_name}
            onClick={() => onSelect(b.place_id)}
            zIndex={isSelected ? 1000 : isHighlighted ? 500 : undefined}
          >
            <div className="relative grid place-items-center">
              {isSelected && (
                <span
                  aria-hidden
                  className="absolute size-6 rounded-full"
                  style={{
                    background: `${meta.color}33`,
                    boxShadow: `0 0 0 6px ${meta.color}1a`,
                  }}
                />
              )}
              {isHighlighted && (
                <span
                  aria-hidden
                  className="absolute size-6 rounded-full animate-pulse-soft"
                  style={{
                    background: `${meta.color}26`,
                    boxShadow: `0 0 0 4px ${meta.color}33`,
                  }}
                />
              )}
              <Pin
                background={meta.color}
                borderColor={meta.border}
                glyphColor={meta.glyph}
                scale={isSelected ? 1.15 : isHighlighted ? 1.08 : 1.0}
              />
            </div>
          </AdvancedMarker>
        );
      })}

      {userLoc && (
        <AdvancedMarker position={userLoc} title="Your location">
          <span
            aria-label="Your location"
            className="relative grid place-items-center"
          >
            <span className="absolute size-5 rounded-full bg-iri-blue/25" />
            <span className="size-3 rounded-full bg-iri-blue ring-2 ring-white" />
          </span>
        </AdvancedMarker>
      )}
    </>
  );
}

function MapFallback() {
  return (
    <div className="size-full grid place-items-center bg-[var(--color-map-land)] text-ink-200 text-sm p-6 text-center">
      <div className="max-w-sm">
        <div className="font-medium text-ink-700">Google Maps key not set</div>
        <p className="text-ink-100 mt-1">
          Set <code className="font-mono text-[12px]">VITE_GOOGLE_MAPS_KEY</code> in{" "}
          <code className="font-mono text-[12px]">web/.env.local</code> to render the
          map. Pins and filtering still work in the floating panel above.
        </p>
      </div>
    </div>
  );
}
