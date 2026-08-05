export default defineNuxtConfig({
  modules: ["@nuxt/content"],
  app: {
    head: {
      title: "Wispr Proxyflow",
      meta: [
        {
          name: "description",
          content: "Wispr Proxyflow — Wispr Flow → Pro: local MITM helper — docs",
        },
      ],
    },
  },
  content: {
    build: {
      markdown: { toc: { depth: 3 } },
    },
  },
  nitro: {
    prerender: {
      routes: [
        "/",
        "/1.introduction",
        "/2.installation",
        "/3.usage",
        "/4.build",
        "/5.architecture",
        "/6.troubleshooting",
      ],
    },
  },
  css: ["~/assets/css/main.css"],
  compatibilityDate: "2024-11-01",
})
