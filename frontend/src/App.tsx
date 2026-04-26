import { lazy, Suspense, useEffect, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from './lib/queryClient'
import { useMe } from './hooks/useMe'
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
const MaintenancePage = lazy(() => import('./pages/MaintenancePage'))

// Roles that trigger the access denied page (unless the user is also an admin).
// Configure via VITE_RESTRICTED_ROLES (comma-separated), e.g.:
//   VITE_RESTRICTED_ROLES=/declic-admin,/adh6-admin
const RESTRICTED_ROLES: string[] = (import.meta.env.VITE_RESTRICTED_ROLES ?? '')
  .split(',')
  .map((r: string) => r.trim().replace(/^\//, ''))
  .filter(Boolean)

const IS_PREPROD = import.meta.env.VITE_APP_ENV === 'preprod'

function accessDeniedReason(me: { is_admin: boolean; groups: string[]; ldap_login?: string | null }): 'preprod' | 'restricted' | null {
  if (me.is_admin) return null
  if (IS_PREPROD && !me.ldap_login) return 'preprod'
  if (RESTRICTED_ROLES.length > 0 && me.groups.some((g) => RESTRICTED_ROLES.includes(g))) return 'restricted'
  return null
}

function PageFallback() {
  const { t } = useTranslation()
  return <div className="flex items-center justify-center h-full text-xs text-neutral-400 dark:text-neutral-500">{t('loading')}</div>
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

  if (auth.me.wifi_only === true) return <AccessDenied reason="wifi_only" />

  const denied = accessDeniedReason(auth.me)
  if (denied) return <AccessDenied reason={denied} />

  if (!auth.me.is_admin && auth.me.maintenance) {
    return <Suspense fallback={null}><MaintenancePage /></Suspense>
  }

  if (!auth.me.is_admin && !auth.me.date_signed_hosting) {
    return <CharterPage onSigned={auth.refresh} />
  }

  if (auth.me.is_admin) {
    return (
      <QueryClientProvider client={queryClient}>
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
      </QueryClientProvider>
    )
  }

  return (
    <QueryClientProvider client={queryClient}>
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
    </QueryClientProvider>
  )
}
