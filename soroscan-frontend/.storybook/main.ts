import { fileURLToPath } from "node:url";
import type { StorybookConfig } from "@storybook/nextjs-vite";

const config: StorybookConfig = {
  stories: ["../components/**/*.stories.@(ts|tsx)", "../app/**/*.stories.@(ts|tsx)"],
  framework: {
    name: "@storybook/nextjs-vite",
    options: {},
  },
  staticDirs: ["../public"],
  // Mirror the "@/*" path alias from tsconfig.json
  viteFinal: async (viteConfig) => {
    viteConfig.resolve ??= {};
    viteConfig.resolve.alias = {
      ...viteConfig.resolve.alias,
      "@": fileURLToPath(new URL("..", import.meta.url)),
    };
    return viteConfig;
  },
};

export default config;
