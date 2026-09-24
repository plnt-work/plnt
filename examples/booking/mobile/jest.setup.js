// Jest setup — wires the official AsyncStorage mock so persisted
// zustand stores + identity helpers behave in test runs.
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);
