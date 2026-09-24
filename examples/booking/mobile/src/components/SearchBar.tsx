// Home search bar. Submitting routes the raw text through the WS to
// classify_intent — same path as web Atlas's freeform search. No
// suggestions / autocomplete in P1 (would be vibe code without data).
import { useState } from "react";
import { Pressable, TextInput, View } from "react-native";
import { Search } from "lucide-react-native";

interface Props {
  placeholder?: string;
  onSubmit: (text: string) => void;
}

export function SearchBar({ placeholder = "Try “haircut tonight”", onSubmit }: Props) {
  const [value, setValue] = useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
    setValue("");
  };

  return (
    <View className="flex-row items-center gap-2 px-3 py-2 bg-white border border-paper-500 rounded-2xl">
      <Search size={18} color="#6C6A60" />
      <TextInput
        value={value}
        onChangeText={setValue}
        placeholder={placeholder}
        placeholderTextColor="#9A968C"
        returnKeyType="search"
        onSubmitEditing={submit}
        className="flex-1 text-ink-800 text-base py-1"
      />
      <Pressable
        onPress={submit}
        className="px-3 py-1 bg-ink-800 rounded-xl"
        accessibilityRole="button"
      >
        <Search size={16} color="#FBF7EE" />
      </Pressable>
    </View>
  );
}
