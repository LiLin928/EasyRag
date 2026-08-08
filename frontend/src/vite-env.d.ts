/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE: string
  readonly VITE_USE_MOCK: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

// axios 官方导出的深路径（见其 package.json 的 exports），但未随包提供类型声明
declare module 'axios/lib/adapters/xhr.js' {
  import type { AxiosAdapter } from 'axios'
  const adapter: AxiosAdapter
  export default adapter
}
