import { lazy, Suspense, useEffect, type ReactNode } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useMe } from './useMe'
import { loginUrl } from './api'
import Layout from './components/Layout'
import AdminLayout from './components/AdminLayout'
import AccessDenied from './pages/AccessDenied'
import CharterPage from './pages/CharterPage'
import { UserProvider } from './contexts/UserContext'
import { VMStatusProvider } from './contexts/VMStatusContext'
import { ToastProvider } from './contexts/ToastContext'
import ToastContainer from './components/ToastContainer'
import ErrorBoundary from './components/ErrorBoundary'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const VMPage = lazy(() => import('./pages/VMPage'))
const AdminPage = lazy(() => import('./pages/AdminPage'))

// Roles that trigger the access denied page (unless the user is also an admin).
// Configure via VITE_RESTRICTED_ROLES (comma-separated), e.g.:
//   VITE_RESTRICTED_ROLES=/declic-admin,/adh6-admin
const RESTRICTED_ROLES: string[] = (import.meta.env.VITE_RESTRICTED_ROLES ?? '')
  .split(',')
  .map((r: string) => r.trim().replace(/^\//, ''))
  .filter(Boolean)

const DEV_MODE = import.meta.env.DEV

function isAccessDenied(me: { is_admin: boolean; groups: string[]; ldap_login?: string | null }): boolean {
  if (me.is_admin) return false
  if (DEV_MODE && !me.ldap_login) return true
  return RESTRICTED_ROLES.length > 0 && me.groups.some((g) => RESTRICTED_ROLES.includes(g))
}

function PageFallback() {
  return <div className="flex items-center justify-center h-full text-xs text-neutral-400">Chargement…</div>
}

function RouteBoundary({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  return <ErrorBoundary resetKey={pathname}>{children}</ErrorBoundary>
}

export default function App() {
  const auth = useMe()

  useEffect(() => {
    if (auth.status === 'unauthenticated') {
      window.location.href = loginUrl()
    }
  }, [auth.status])

  if (auth.status !== 'authenticated') return null

  if (isAccessDenied(auth.me)) return <AccessDenied />

  if (!auth.me.is_admin && !auth.me.date_signed_hosting) {
    return <CharterPage onSigned={auth.refresh} />
  }

  if (auth.me.is_admin) {
    return (
      <ToastProvider>
        <UserProvider me={auth.me}>
          <VMStatusProvider>
            <BrowserRouter>
              <AdminLayout>
                <RouteBoundary>
                  <Suspense fallback={<PageFallback />}>
                    <Routes>
                      <Route path="/admin" element={<AdminPage />} />
                      <Route path="/vm/:vmId" element={<VMPage />} />
                      <Route path="*" element={<Navigate to="/admin" replace />} />
                    </Routes>
                  </Suspense>
                </RouteBoundary>
              </AdminLayout>
            </BrowserRouter>
          </VMStatusProvider>
        </UserProvider>
        <ToastContainer />
      </ToastProvider>
    )
  }

  return (
    <ToastProvider>
      <UserProvider me={auth.me}>
        <VMStatusProvider>
          <BrowserRouter>
            <Layout>
              <RouteBoundary>
                <Suspense fallback={<PageFallback />}>
                  <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/vm/:vmId" element={<VMPage />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </Suspense>
              </RouteBoundary>
            </Layout>
          </BrowserRouter>
        </VMStatusProvider>
      </UserProvider>
      <ToastContainer />
    </ToastProvider>
  )
}
