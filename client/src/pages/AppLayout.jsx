import React, { useEffect } from 'react'
import { useStore } from '../store'
import ContactList from '../ui/ContactList'
import ChatReader from '../ui/ChatReader'
import AIAgentChat from './AIAgentChat'
import Navbar from '../components/Navbar'
import { getSocket } from '../lib/sockets'
import { handleWebhookPayload } from '../lib/automation'

export default function AppLayout() {
  const autoReplyEnabled = useStore(s => s.autoReplyEnabled)
  const setAutoReplyEnabled = useStore(s => s.setAutoReplyEnabled)

  const clearAllChats = () => {
    if (window.confirm('Clear all chat histories? This cannot be undone.')) {
      useStore.setState({ chats: {} })
    }
  }

  useEffect(() => {
    const socket = getSocket()
    socket.on('connect', () => console.log('socket connected'))
    socket.on('newMessage', (payload) => { handleWebhookPayload(payload) })
    return () => {
      socket.off('newMessage')
    }
  }, [])

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Fixed Navbar */}
      <Navbar />

      {/* Main content with top padding for fixed navbar */}
      <div className="flex-1 overflow-hidden pt-16">
        {/* Top bar with controls */}
        <div className="border-b bg-white px-4 py-3 flex items-center justify-end space-x-4">
          <button
            onClick={clearAllChats}
            className="text-xs text-red-600 hover:text-red-800 px-3 py-2 border border-red-300 rounded-lg hover:bg-red-50 transition-colors"
            title="Clear all chat histories"
          >
            Clear All Chats
          </button>
          <label className="text-sm text-gray-700 flex items-center gap-2">
            <span>Auto-Reply</span>
            <input 
              type="checkbox" 
              checked={autoReplyEnabled} 
              onChange={e=>setAutoReplyEnabled(e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
          </label>
        </div>

        {/* Layout: Left = contacts/chat, Right = AI Agent */}
        <div className="h-full grid grid-cols-12 overflow-hidden">
          <div className="col-span-5 border-r flex overflow-hidden">
            <div className="w-1/2 border-r overflow-hidden"><ContactList /></div>
            <div className="w-1/2 overflow-hidden"><ChatReader /></div>
          </div>
          <div className="col-span-7 overflow-hidden">
            <AIAgentChat />
          </div>
        </div>
      </div>
    </div>
  )
}
