// Filter drawer — gorhom bottom-sheet modal. Stub fields per spec:
// vertical, min rating, max distance. Submitting writes back to the
// shared search store; the parent screen re-renders off useSearch().
import { forwardRef, useCallback, useImperativeHandle, useMemo, useRef, useState } from "react";
import { Pressable, Text, View } from "react-native";
import {
  BottomSheetModal,
  BottomSheetBackdrop,
  type BottomSheetBackdropProps,
} from "@gorhom/bottom-sheet";
// `BottomSheetModal` is the COMPONENT (named export). Its ref type is
// also `BottomSheetModal` — TS unifies them, no separate type alias.
type BottomSheetModalRef = BottomSheetModal;
import type { Vertical } from "@web/places/types";
import { CATEGORIES } from "@/features/places/categories";

const BRAND_VIOLET = "#A672E0";

export interface FilterDrawerHandle {
  open: () => void;
  close: () => void;
}

export interface FilterValue {
  vertical: Vertical | null;
  minRating: number;
  maxKm: number;
}

interface Props {
  initial: FilterValue;
  onApply: (next: FilterValue) => void;
}

const RATINGS = [0, 3.5, 4.0, 4.5];
const DISTANCES = [1, 3, 5, 10];

export const FilterDrawer = forwardRef<FilterDrawerHandle, Props>(
  function FilterDrawer({ initial, onApply }, ref) {
    const modalRef = useRef<BottomSheetModalRef>(null);
    const [draft, setDraft] = useState<FilterValue>(initial);
    const snapPoints = useMemo(() => ["55%"], []);

    useImperativeHandle(ref, () => ({
      open: () => {
        setDraft(initial);
        modalRef.current?.present();
      },
      close: () => modalRef.current?.dismiss(),
    }));

    const renderBackdrop = useCallback(
      (props: BottomSheetBackdropProps) => (
        <BottomSheetBackdrop
          {...props}
          appearsOnIndex={0}
          disappearsOnIndex={-1}
          opacity={0.4}
        />
      ),
      [],
    );

    const apply = () => {
      onApply(draft);
      modalRef.current?.dismiss();
    };

    return (
      <BottomSheetModal
        ref={modalRef}
        snapPoints={snapPoints}
        backdropComponent={renderBackdrop}
        handleIndicatorStyle={{ backgroundColor: "#B6AE96" }}
      >
        <View className="px-4 pt-2 pb-4">
          <Text className="text-ink-800 text-lg font-semibold mb-3">Filters</Text>

          {/* Vertical */}
          <Text className="text-ink-500 text-xs uppercase tracking-wider mb-2">Type</Text>
          <View className="flex-row flex-wrap mb-4">
            {CATEGORIES.map((c) => {
              const active = (draft.vertical || null) === c.vertical;
              return (
                <Pressable
                  key={c.key}
                  onPress={() => setDraft({ ...draft, vertical: c.vertical })}
                  style={{
                    backgroundColor: active ? BRAND_VIOLET : "#F8F2E0",
                  }}
                  className="px-3 py-1.5 mr-2 mb-2 rounded-full"
                >
                  <Text
                    className={
                      "text-xs font-medium " + (active ? "text-white" : "text-ink-800")
                    }
                  >
                    {c.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          {/* Min rating */}
          <Text className="text-ink-500 text-xs uppercase tracking-wider mb-2">Min rating</Text>
          <View className="flex-row mb-4">
            {RATINGS.map((r) => {
              const active = draft.minRating === r;
              return (
                <Pressable
                  key={r}
                  onPress={() => setDraft({ ...draft, minRating: r })}
                  style={{
                    backgroundColor: active ? BRAND_VIOLET : "#F8F2E0",
                  }}
                  className="px-3 py-1.5 mr-2 rounded-full"
                >
                  <Text
                    className={
                      "text-xs font-medium " + (active ? "text-white" : "text-ink-800")
                    }
                  >
                    {r === 0 ? "Any" : `${r.toFixed(1)}+`}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          {/* Distance */}
          <Text className="text-ink-500 text-xs uppercase tracking-wider mb-2">Within</Text>
          <View className="flex-row mb-6">
            {DISTANCES.map((d) => {
              const active = draft.maxKm === d;
              return (
                <Pressable
                  key={d}
                  onPress={() => setDraft({ ...draft, maxKm: d })}
                  style={{
                    backgroundColor: active ? BRAND_VIOLET : "#F8F2E0",
                  }}
                  className="px-3 py-1.5 mr-2 rounded-full"
                >
                  <Text
                    className={
                      "text-xs font-medium " + (active ? "text-white" : "text-ink-800")
                    }
                  >
                    {d} km
                  </Text>
                </Pressable>
              );
            })}
          </View>

          <Pressable
            onPress={apply}
            className="bg-ink-800 rounded-2xl py-3 items-center"
          >
            <Text className="text-paper-100 font-semibold text-sm">Apply</Text>
          </Pressable>
        </View>
      </BottomSheetModal>
    );
  },
);
