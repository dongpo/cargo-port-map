import {defineConfig} from 'vite';
export default defineConfig(({mode})=>({base:mode==='pages'?'/cargo-port-map/':'/',server:{host:'127.0.0.1',fs:{deny:['.env','.env.*','*.{crt,pem}','**/.git/**','**/data/*.sqlite*','**/data/*.jsonl.gz']}},build:{rollupOptions:{output:{manualChunks:{maplibre:['maplibre-gl']}}}}}));
