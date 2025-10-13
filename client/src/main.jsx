import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'
import Landing from './pages/Landing'
import AppLayout from './pages/AppLayout'
import BusinessDescription from './pages/BusinessDescription'
import { useStore } from './store'

function RouterGuard() {
  const credentials = useStore((s) => s.credentials)
  if (!credentials?.whatsappToken || !credentials?.phoneNumberId || !credentials?.businessAccountId) {
    return <Navigate to="/" replace />
  }
  return <AppLayout />
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<RouterGuard />} />
        <Route path="/business-description" element={<BusinessDescription />} />
  {/* Todo page removed */}
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
)
