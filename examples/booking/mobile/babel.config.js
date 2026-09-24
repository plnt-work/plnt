// IMPORTANT (prior-app lesson HDGEcalls):
//   babel-preset-expo with jsxImportSource:'nativewind' MUST come first,
//   then 'nativewind/babel'. Swapping breaks Metro.
module.exports = function (api) {
  api.cache(true);
  return {
    presets: [
      ["babel-preset-expo", { jsxImportSource: "nativewind" }],
      "nativewind/babel",
    ],
    plugins: [
      // Reanimated must be last.
      "react-native-reanimated/plugin",
    ],
  };
};
