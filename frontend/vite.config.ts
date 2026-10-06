import { defineConfig } from "vite";

// Builds one self-contained ES module that Home Assistant loads as the panel's module_url.
export default defineConfig({
  build: {
    lib: {
      entry: "src/panel.ts",
      formats: ["es"],
      fileName: () => "shelly-elevate-panel.js",
    },
    // Relative to this directory (the Vite root); keep the other files in that folder.
    outDir: "../custom_components/shellyelevateintegration/frontend",
    emptyOutDir: false,
    target: "es2021",
    rolldownOptions: {
      output: {
        codeSplitting: false,
        // Vite does not minify ES library builds; this is an application bundle, so let
        // rolldown minify it completely.
        minify: true,
        comments: { legal: false, annotation: false, jsdoc: false },
      },
    },
  },
});
