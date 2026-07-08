import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    '[Crisis Data Terminal] 缺少 Supabase 环境变量：请在项目根目录 .env 中配置 VITE_SUPABASE_URL 和 VITE_SUPABASE_ANON_KEY，然后重启 npm run dev。',
  )
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
