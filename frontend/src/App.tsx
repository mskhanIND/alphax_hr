import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
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
const Setup = lazy(() => import('./pages/Setup'))
const RecordView = lazy(() => import('./pages/RecordView'))
const ContractPage = lazy(() => import('./pages/Contract'))
const LeaveBalances = lazy(() => import('./pages/LeaveBalances'))
const AttendancePage = lazy(() => import('./pages/Attendance'))
const Payroll = lazy(() => import('./pages/Payroll'))
const Gosi = lazy(() => import('./pages/Gosi'))
const Eosb = lazy(() => import('./pages/Eosb'))
const MyRequests = lazy(() => import('./pages/MyRequests'))
const Requests = lazy(() => import('./pages/Requests'))
const Penalties = lazy(() => import('./pages/Penalties'))
const MyPenalties = lazy(() => import('./pages/MyPenalties'))
const Settlements = lazy(() => import('./pages/Settlements'))
const Appraisals = lazy(() => import('./pages/Appraisals'))
const Cutover = lazy(() => import('./pages/Cutover'))
const Services = lazy(() => import('./pages/Services'))
const MyExpenses = lazy(() => import('./pages/MyExpenses'))
const MyDocuments = lazy(() => import('./pages/MyDocuments'))
const MyTeam = lazy(() => import('./pages/MyTeam'))
const MyPerformance = lazy(() => import('./pages/MyPerformance'))
const AttendancePolicies = lazy(() => import('./pages/AttendancePolicies'))
const NotificationsAdmin = lazy(() => import('./pages/NotificationsAdmin'))
const ApprovalDelays = lazy(() => import('./pages/ApprovalDelays'))
const ApprovalPolicies = lazy(() => import('./pages/ApprovalPolicies'))
const TeamAppraisals = lazy(() => import('./pages/TeamAppraisals'))
const Loans = lazy(() => import('./pages/Loans'))
const MyLoans = lazy(() => import('./pages/MyLoans'))
const PayAdjustments = lazy(() => import('./pages/PayAdjustments'))
const BulkUpdate = lazy(() => import('./pages/BulkUpdate'))
const Accruals = lazy(() => import('./pages/Accruals'))
const VacationPlan = lazy(() => import('./pages/VacationPlan'))
const VacationPlanner = lazy(() => import('./pages/VacationPlanner'))
const AnnouncementsAdmin = lazy(() => import('./pages/AnnouncementsAdmin'))
const Checkins = lazy(() => import('./pages/Checkins'))
const WorkLocations = lazy(() => import('./pages/WorkLocations'))
const AttendanceDevices = lazy(() => import('./pages/AttendanceDevices'))
const HelpCentre = lazy(() => import('./pages/HelpCentre'))
const KnowledgeAdmin = lazy(() => import('./pages/KnowledgeAdmin'))

function Guard({ when, children }: { when: (s: ReturnType<typeof useSession>) => boolean; children: ReactNode }) {
  const s = useSession()
  const loc = useLocation()
  // Pages HR switched off (HR status & setup → Settings → Pages)
  if ((s.hidden_pages ?? []).some((p) => loc.pathname === p || loc.pathname.startsWith(p + '/'))) return <Navigate to="/" replace />
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
            <Route path="/me/services" element={<Guard when={emp}><Services /></Guard>} />
            <Route path="/me/expenses" element={<Guard when={emp}><MyExpenses /></Guard>} />
            <Route path="/me/documents" element={<Guard when={emp}><MyDocuments /></Guard>} />
            <Route path="/me/performance" element={<Guard when={emp}><MyPerformance /></Guard>} />
            <Route path="/me/vacation-plan" element={<Guard when={emp}><VacationPlan /></Guard>} />
            <Route path="/vacation-planner" element={<Guard when={mgr}><VacationPlanner /></Guard>} />
            <Route path="/attendance-policies" element={<Guard when={hr}><AttendancePolicies /></Guard>} />
            <Route path="/me/help" element={<Guard when={emp}><HelpCentre /></Guard>} />
            <Route path="/knowledge" element={<Guard when={hr}><KnowledgeAdmin /></Guard>} />
            <Route path="/checkins" element={<Guard when={mgr}><Checkins /></Guard>} />
            <Route path="/work-locations" element={<Guard when={hr}><WorkLocations /></Guard>} />
            <Route path="/attendance-devices" element={<Guard when={hr}><AttendanceDevices /></Guard>} />
            <Route path="/approval-policies" element={<Guard when={hr}><ApprovalPolicies /></Guard>} />
            <Route path="/announcements" element={<Guard when={hr}><AnnouncementsAdmin /></Guard>} />
            <Route path="/my-team" element={<Guard when={mgr}><MyTeam /></Guard>} />
            <Route path="/me/requests" element={<Guard when={emp}><MyRequests /></Guard>} />
            <Route path="/penalties" element={<Guard when={hr}><Penalties /></Guard>} />
            <Route path="/me/warnings" element={<Guard when={emp}><MyPenalties /></Guard>} />
            <Route path="/requests" element={<Guard when={hr}><Requests /></Guard>} />
            <Route path="/me/profile" element={<Guard when={emp}><MyProfile /></Guard>} />
            <Route path="/approvals" element={<Guard when={mgr}><Approvals /></Guard>} />
            <Route path="/approval-delays" element={<Guard when={mgr}><ApprovalDelays /></Guard>} />
            <Route path="/team-appraisals" element={<Guard when={mgr}><TeamAppraisals /></Guard>} />
            <Route path="/people/bulk-update" element={<Guard when={hr}><BulkUpdate /></Guard>} />
            <Route path="/payroll/accruals" element={<Guard when={hr}><Accruals /></Guard>} />
            <Route path="/payroll/loans" element={<Guard when={hr}><Loans /></Guard>} />
            <Route path="/payroll/adjustments" element={<Guard when={hr}><PayAdjustments /></Guard>} />
            <Route path="/me/loans" element={<Guard when={emp}><MyLoans /></Guard>} />
            <Route path="/notifications-setup" element={<Guard when={hr}><NotificationsAdmin /></Guard>} />
            <Route path="/team" element={<Guard when={mgr}><TeamCalendar /></Guard>} />
            <Route path="/people" element={<Guard when={hr}><People /></Guard>} />
            <Route path="/people/new" element={<Guard when={hr}><NewEmployee /></Guard>} />
            <Route path="/people/:id" element={<Guard when={hr}><EmployeeDetail /></Guard>} />
            <Route path="/compliance" element={<Guard when={hr}><Compliance /></Guard>} />
            <Route path="/leave-setup" element={<Guard when={hr}><LeaveSetup /></Guard>} />
            <Route path="/roster" element={<Guard when={hr}><Roster /></Guard>} />
            <Route path="/activity" element={<Guard when={hr}><ActivityLog /></Guard>} />
            <Route path="/r/:doctype/:name" element={<RecordView />} />
            <Route path="/people/:id/contract" element={<Guard when={hr}><ContractPage /></Guard>} />
            <Route path="/setup" element={<Guard when={(x: any) => x.persona.hr || x.persona.system_manager}><Setup /></Guard>} />
            <Route path="/leave-balances" element={<Guard when={hr}><LeaveBalances /></Guard>} />
            <Route path="/attendance" element={<Guard when={hr}><AttendancePage /></Guard>} />
            <Route path="/payroll" element={<Guard when={hr}><Payroll /></Guard>} />
            <Route path="/payroll/gosi" element={<Guard when={hr}><Gosi /></Guard>} />
            <Route path="/payroll/settlements" element={<Guard when={hr}><Settlements /></Guard>} />
            <Route path="/appraisals" element={<Guard when={hr}><Appraisals /></Guard>} />
            <Route path="/cutover" element={<Guard when={(x: any) => x.persona.hr_manager}><Cutover /></Guard>} />
            <Route path="/payroll/eosb" element={<Guard when={hr}><Eosb /></Guard>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </Layout>
    </SessionProvider>
  )
}
