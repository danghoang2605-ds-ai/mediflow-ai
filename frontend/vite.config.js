import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

export default defineConfig({
  plugins: [react()],
  base: '/medparcours-ai/', // ĐỔI TÊN Ở DÒNG NÀY
  server: { port: 5173 },
})
