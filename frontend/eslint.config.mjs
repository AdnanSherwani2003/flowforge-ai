import js from "@eslint/js";
import tseslint from "typescript-eslint";
import { defineConfig, globalIgnores } from "eslint/config";
export default defineConfig([
 js.configs.recommended, ...tseslint.configs.recommended,
 {rules:{"no-undef":"off"}},
 globalIgnores([".next/**","next-env.d.ts","coverage/**","test-results/**","playwright-report/**"])
]);
