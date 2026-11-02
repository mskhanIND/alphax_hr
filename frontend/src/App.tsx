import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ErrorBox, Spinner } from './components/ui'
import { SessionProvider, useSession, useSessionQuery } from './lib/session'
import Home from './pages/Home'

const MyLeave = lazy(() => import('./pages/MyLeave'))
const MyAttendance = lazy(() => import('./pages/MyAttendance'))
const MyPayslips = lazy(() => import('./pages/MyPayslips'))
const MyProfile = lazy(() => import('./pages/MyProfile'))
const Approvals = lazy(() => import('./pages/Approvals'))
const TeamCalendar = lazy(() => import('./pages/TeamCalendar'))
const People = lazy(() => import('./pages/People'))
const EmployeeDetail = lazy(() => import('./pages/EmployeeDetail'))
const NewEmployee = lazy(() => import('./pages/NewEmployee'))
const Compliance = lazy(() => import('./pages/Compliance'))
const LeaveSetup = lazy(() => import('./pages/LeaveSetup'))
const Roster = lazy(() => import('./pages/Roster'))
const ActivityLog = lazy(() => import('./pages/ActivityLog'))
const LeaveBalances = lazy(() => import('./pages/LeaveBalances'))
const AttendancePage = lazy(() => import('./pages/Attendance'))
const Payroll = lazy(() => import('./pages/Payroll'))
const Gosi = lazy(() => import('./pages/Gosi'))
const Eosb = lazy(() => import('./pages/Eosb'))

function Guard({ when, children }: { when: (s: ReturnType<typeof useSession>) => boolean; children: ReactNode }) {
  const s = useSession()
  return when(s) ? <>{children}</> : <Navigate to="/" replace />
}

export default function App() {
  const q = useSessionQuery()
  if (q.isLoading) return <Spinner />
  if (q.error || !q.data) return <div className="p-6"><ErrorBox error={q.error} onRetry={() => q.refetch()} /></div>
  const emp = (s: any) => s.persona.employee
  const mgr = (s: any) => s.persona.approver || s.persona.hr
  const hr = (s: any) => s.persona.hr
  return (
    <SessionProvider session={q.data}>
      <Layout>
        <Suspense fallback={<Spinner />}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/me/leave" element={<Guard when={emp}><MyLeave /></Guard>} />
            <Route path="/me/attendance" element={<Guard when={emp}><MyAttendance /></Guard>} />
            <Route path="/me/payslips" element={<Guard when={emp}><MyPayslips /></Guard>} />
            <Route path="/me/profile" element={<Guard when={emp}><MyProfile /></Guard>} />
            <Route path="/approvals" element={<Guard when={mgr}><Approvals /></Guard>} />
            <Route path="/team" element={<Guard when={mgr}><TeamCalendar /></Guard>} />
            <Route path="/people" element={<Guard when={hr}><People /></Guard>} />
            <Route path="/people/new" element={<Guard when={hr}><NewEmployee /></Guard>} />
            <Route path="/people/:id" element={<Guard when={hr}><EmployeeDetail /></Guard>} />
            <Route path="/compliance" element={<Guard when={hr}><Compliance /></Guard>} />
            <Route path="/leave-setup" element={<Guard when={hr}><LeaveSetup /></Guard>} />
            <Route path="/roster" element={<Guard when={hr}><Roster /></Guard>} />
            <Route path="/activity" element={<Guard when={hr}><ActivityLog /></Guard>} />
            <Route path="/leave-balances" element={<Guard when={hr}><LeaveBalances /></Guard>} />
            <Route path="/attendance" element={<Guard when={hr}><AttendancePage /></Guard>} />
            <Route path="/payroll" element={<Guard when={hr}><Payroll /></Guard>} />
            <Route path="/payroll/gosi" element={<Guard when={hr}><Gosi /></Guard>} />
            <Route path="/payroll/eosb" element={<Guard when={hr}><Eosb /></Guard>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </Layout>
    </SessionProvider>
  )
}
