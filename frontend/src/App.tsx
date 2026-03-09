import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useMe } from './useMe'
import { loginUrl } from './api'
import Layout from './components/Layout'
import AdminLayout from './components/AdminLayout'
import Dashboard from './pages/Dashboard'
import VMPage from './pages/VMPage'
import AdminPage from './pages/AdminPage'
import AccessDenied from './pages/AccessDenied'
import CharterPage from './pages/CharterPage'
import { UserProvider } from './contexts/UserContext'
import { VMStatusProvider } from './contexts/VMStatusContext'
import { ToastProvider } from './contexts/ToastContext'
import ToastContainer from './components/ToastContainer'

// Roles that trigger the access denied page (unless the user is also an admin).
// Configure via VITE_RESTRICTED_ROLES (comma-separated), e.g.:
//   VITE_RESTRICTED_ROLES=/declic-admin,/adh6-admin
const RESTRICTED_ROLES: string[] = (import.meta.env.VITE_RESTRICTED_ROLES ?? '')
  .split(',')
  .map((r: string) => r.trim())
  .filter(Boolean)

function isAccessDenied(me: { is_admin: boolean; groups: string[] }): boolean {
  if (me.is_admin) return false
  return RESTRICTED_ROLES.length > 0 && me.groups.some((g) => RESTRICTED_ROLES.includes(g))
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
                <Routes>
                  <Route path="/admin" element={<AdminPage />} />
                  <Route path="*" element={<Navigate to="/admin" replace />} />
                </Routes>
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
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/vm/:vmId" element={<VMPage />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Layout>
          </BrowserRouter>
        </VMStatusProvider>
      </UserProvider>
      <ToastContainer />
    </ToastProvider>
  )
}
