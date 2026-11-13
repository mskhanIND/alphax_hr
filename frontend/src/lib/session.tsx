import { createContext, useContext, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from './api'

export interface Session {
  user: string
  full_name: string
  user_image?: string | null
  roles: string[]
  persona: { employee: boolean; approver: boolean; hr: boolean; hr_manager: boolean; system_manager?: boolean; manager?: boolean; management?: boolean }
  employee: null | { name: string; employee_name: string; image?: string; designation?: string; department?: string; company?: string; date_of_joining?: string }
  company?: string
  title: string
  hidden_pages?: string[]
  desk?: boolean
  brand?: { title: string; tagline: string; logo: string; icon: string; custom: boolean }
  version: string
  gosi_enabled: boolean
  legacy_hr?: boolean
}

const Ctx = createContext<Session | null>(null)

export function useSessionQuery() {
  return useQuery<Session>({ queryKey: ['boot'], queryFn: api.boot, staleTime: 5 * 60_000 })
}

export function SessionProvider({ session, children }: { session: Session; children: ReactNode }) {
  return <Ctx.Provider value={session}>{children}</Ctx.Provider>
}

export function useSession() {
  const s = useContext(Ctx)
  if (!s) throw new Error('useSession outside provider')
  return s
}
