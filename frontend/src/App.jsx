import { Routes, Route, Navigate } from 'react-router'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import LoginPage from './pages/LoginPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import UploadPage from './pages/UploadPage.jsx'
import ResultadosPage from './pages/ResultadosPage.jsx'
import EnviosPage from './pages/EnviosPage.jsx'
import CatalogoPage from './pages/CatalogoPage.jsx'
import PerfilesPage from './pages/PerfilesPage.jsx'
import PerfilIndividualPage from './pages/PerfilIndividualPage.jsx'
import QuimicosPage from './pages/QuimicosPage.jsx'
import UsuariosPage from './pages/UsuariosPage.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/upload"
        element={
          <ProtectedRoute>
            <UploadPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/resultados"
        element={
          <ProtectedRoute>
            <ResultadosPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/envios"
        element={
          <ProtectedRoute>
            <EnviosPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/catalogo"
        element={
          <ProtectedRoute>
            <CatalogoPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/perfiles"
        element={
          <ProtectedRoute>
            <PerfilesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/perfiles/:id"
        element={
          <ProtectedRoute>
            <PerfilIndividualPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/quimicos"
        element={
          <ProtectedRoute>
            <QuimicosPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/usuarios"
        element={
          <ProtectedRoute>
            <UsuariosPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
