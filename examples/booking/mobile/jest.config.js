// Jest config — uses jest-expo's preset (handles RN's babel pipeline +
// transform allowlist) and adds the same @/ path alias the app uses.
module.exports = {
  preset: "jest-expo",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
  moduleNameMapper: {
    "^@/(.*)$": "<rootDir>/src/$1",
    "^@web/(.*)$": "<rootDir>/../web/src/features/$1",
  },
  transformIgnorePatterns: [
    "node_modules/(?!(jest-)?react-native|@react-native|expo(nent)?|@expo(nent)?|@expo-google-fonts|react-clone-referenced-element|@react-navigation|@unimodules|sentry-expo|native-base|react-native-svg|nativewind|lucide-react-native|@gorhom/.*|@shopify/.*)",
  ],
  testMatch: ["**/__tests__/**/*.test.[jt]s?(x)"],
};
