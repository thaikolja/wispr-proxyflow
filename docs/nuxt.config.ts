export default defineNuxtConfig({
  extends: "@nuxt-themes/docus",
  app: {
    baseURL: "/wispr-proxyflow/",
  },
  docus: {
    title: "Wispr Proxyflow",
    description: "Wispr Flow → Pro — local MITM helper (educational)",
    url: "https://thaikolja.github.io/wispr-proxyflow/",
    github: {
      repo: "thaikolja/wispr-proxyflow",
      branch: "main",
      root: "docs/content",
    },
  },
  compatibilityDate: "2024-11-01",
})
