// Hero carousel for the venue detail page. Renders the
// `business.photos[]` slots one-per-page via a paged horizontal
// ScrollView (one of expo-image's least-broken pairings in RN). When
// `photos` is missing or empty, falls back to a vertical-colored
// placeholder block — matches the original P1 behavior so screens with
// no curated photo don't regress.
import { useRef, useState } from "react";
import {
  Dimensions,
  NativeScrollEvent,
  NativeSyntheticEvent,
  Pressable,
  ScrollView,
  View,
} from "react-native";
import { Image } from "expo-image";
import type { Business } from "@web/places/types";
import { metaFor } from "@web/places/verticals";

interface Props {
  business: Business;
}

const { width: SCREEN } = Dimensions.get("window");
const HEIGHT = SCREEN * 0.6;

export function VenueHero({ business }: Props) {
  const meta = metaFor(business.vertical);
  const photos = business.photos && business.photos.length > 0 ? business.photos : null;
  const scrollRef = useRef<ScrollView>(null);
  const [index, setIndex] = useState(0);

  if (!photos) {
    return (
      <View>
        <View
          style={{ width: SCREEN, height: HEIGHT, backgroundColor: meta.color }}
        />
      </View>
    );
  }

  const onMomentumEnd = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const next = Math.round(e.nativeEvent.contentOffset.x / SCREEN);
    if (next !== index) setIndex(next);
  };

  const jumpTo = (i: number) => {
    setIndex(i);
    scrollRef.current?.scrollTo({ x: i * SCREEN, animated: true });
  };

  return (
    <View>
      <ScrollView
        ref={scrollRef}
        horizontal
        pagingEnabled
        showsHorizontalScrollIndicator={false}
        onMomentumScrollEnd={onMomentumEnd}
        style={{ width: SCREEN, height: HEIGHT }}
      >
        {photos.map((uri, i) => (
          <Image
            key={`${uri}-${i}`}
            source={{ uri }}
            style={{ width: SCREEN, height: HEIGHT }}
            contentFit="cover"
            cachePolicy="memory-disk"
            transition={200}
          />
        ))}
      </ScrollView>
      {photos.length > 1 ? (
        <View className="flex-row justify-center gap-2 mt-2">
          {photos.map((_, i) => (
            <Pressable
              key={i}
              onPress={() => jumpTo(i)}
              hitSlop={8}
            >
              <View
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: i === index ? "#0E1116" : "#D8CFB4" }}
              />
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}
