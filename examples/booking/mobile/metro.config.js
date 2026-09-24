// Metro config — wraps Expo default with NativeWind + a single extra
// watch folder so we can import the canonical seed/registry files from
// plnt-cloud/web without copying them. The token CSS is read at build
// time by scripts/sync-tokens.mjs and emitted to src/styles/tokens.ts.
const path = require("path");
const { getDefaultConfig } = require("expo/metro-config");
const { withNativeWind } = require("nativewind/metro");

const projectRoot = __dirname;
const repoRoot = path.resolve(projectRoot, "..");

const config = getDefaultConfig(projectRoot);

// Reach into ../web/src/features without copying the seed.
// Metro requires the watch root to include the file; tsconfig paths
// (@web/*) give us a stable import alias the bundler can resolve.
config.watchFolders = [path.resolve(repoRoot, "web/src/features")];

// Constrain node_modules resolution to the mobile project (don't let
// metro climb into web/'s node_modules and double-resolve react).
config.resolver.nodeModulesPaths = [path.resolve(projectRoot, "node_modules")];
config.resolver.disableHierarchicalLookup = true;

module.exports = withNativeWind(config, { input: "./global.css" });
