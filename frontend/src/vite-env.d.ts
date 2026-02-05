/// <reference types="vite/client" />

// Vite ?url import for worker and other assets (resolved at build time)
declare module '*?url' {
  const src: string;
  export default src;
}
