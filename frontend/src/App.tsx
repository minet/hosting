import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useMe } from './useMe'
import { loginUrl } from './api'
import Layout from './components/Layout'
import AdminLayout from './components/AdminLayout'
import Dashboard from './pages/Dashboard'
import VMPage from './pages/VMPage'
import AdminPage from './pages/AdminPage'
import { UserProvider } from './contexts/UserContext'
import { VMStatusProvider } from './contexts/VMStatusContext'

export default function App() {
  const auth = useMe()

  useEffect(() => {
    if (auth.status === 'unauthenticated') {
      window.location.href = loginUrl()
    }
  }, [auth.status])

  if (auth.status !== 'authenticated') return null

  if (auth.me.is_admin) {
    return (
      <UserProvider me={auth.me}>
        <BrowserRouter>
          <AdminLayout>
            <Routes>
              <Route path="/admin" element={<AdminPage />} />
              <Route path="*" element={<Navigate to="/admin" replace />} />
            </Routes>
          </AdminLayout>
        </BrowserRouter>
      </UserProvider>
    )
  }

  return (
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
  )
}
