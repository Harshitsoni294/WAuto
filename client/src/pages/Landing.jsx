import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store'
import { api } from '../lib/api'

export default function Landing() {
  const navigate = useNavigate()
  const setCredentials = useStore(s => s.setCredentials)
  const [whatsappToken, setWhatsappToken] = useState('')
  const [phoneNumberId, setPhoneNumberId] = useState('')
  const [businessAccountId, setBusinessAccountId] = useState('')
  const [serverUrl, setServerUrl] = useState(import.meta.env.VITE_SERVER_URL || 'http://localhost:4000')
  // Google tokens are handled via server OAuth; no manual inputs

  const handleSave = () => {
    setCredentials({ whatsappToken, phoneNumberId, businessAccountId, serverUrl })
    navigate('/app')
  }

  const handleGoogleConnect = async () => {
    try {
      // Use the configured backend URL; fall back to env
      const base = serverUrl || import.meta.env.VITE_SERVER_URL || 'http://localhost:4000'
      // Directly hit the server OAuth endpoint; it will redirect to Google
      window.open(`${base}/auth/google`, '_blank')
    } catch (e) {
      console.error('Google connect error', e)
      alert('Error starting Google connect flow')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="w-full max-w-xl bg-white rounded-lg shadow p-6 space-y-4">
        <h1 className="text-2xl font-bold">WhatsApp Business Automation – Setup</h1>
        <label className="block">
          <span className="text-sm text-gray-600">WHATSAPP_TOKEN</span>
          <input value={whatsappToken} onChange={e=>setWhatsappToken(e.target.value)} className="mt-1 w-full border rounded p-2" placeholder="EAAG..." />
        </label>
        <label className="block">
          <span className="text-sm text-gray-600">PHONE_NUMBER_ID</span>
          <input value={phoneNumberId} onChange={e=>setPhoneNumberId(e.target.value)} className="mt-1 w-full border rounded p-2" placeholder="1234567890" />
        </label>
        <label className="block">
          <span className="text-sm text-gray-600">WHATSAPP_BUSINESS_ACCOUNT_ID</span>
          <input value={businessAccountId} onChange={e=>setBusinessAccountId(e.target.value)} className="mt-1 w-full border rounded p-2" placeholder="1234567890" />
        </label>
        <label className="block">
          <span className="text-sm text-gray-600">Backend URL</span>
          <input value={serverUrl} onChange={e=>setServerUrl(e.target.value)} className="mt-1 w-full border rounded p-2" placeholder="http://localhost:4000" />
        </label>

        <div className="bg-gray-100 p-3 rounded">
          <div className="text-sm text-gray-700">Webhook URL</div>
          <div className="font-mono text-sm">{serverUrl}/webhook</div>
        </div>

        <div className="bg-gray-50 p-3 rounded space-y-2">
          <div className="font-semibold">Google Calendar</div>
          <div className="text-sm text-gray-600">Connect your Google account. Tokens are stored securely on the server.</div>
          <button type="button" onClick={handleGoogleConnect} className="px-3 py-2 bg-red-600 text-white rounded block mx-auto">Connect with Google</button>
          <div className="text-xs text-gray-500">If already connected, the server will use saved tokens automatically.</div>
        </div>

        <button onClick={handleSave} className="w-full bg-green-600 text-white rounded p-2">Save and Start</button>

        <p className="text-xs text-gray-500">Use the verify token you set on the server when configuring Meta Webhooks.</p>
      </div>
    </div>
  )
}
