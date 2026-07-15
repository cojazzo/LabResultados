import { Navigate, useLocation } from 'react-router'
import Layout from './Layout.jsx'

export default function ProtectedRoute({ children }) {
  const location = useLocation()
  const token = localStorage.getItem('lab_token')

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <Layout>{children}</Layout>
}
