import React, { useMemo, useState } from 'react'
import { useStore } from '../store'
import { api } from '../lib/api'
import { addMessageToVectorStore } from '../lib/rag'

export default function ChatReader() {
  const activeChatId = useStore(s => s.activeChatId)
  const chats = useStore(s => s.chats)
  const contacts = useStore(s => s.contacts)
  const contact = contacts.find(c => c.id === activeChatId)
  const [input, setInput] = useState('')
  const autoReplyContacts = useStore(s => s.autoReplyContacts)
  const setContactAutoReply = useStore(s => s.setContactAutoReply)
  const credentials = useStore(s => s.credentials)
  const addMessage = useStore(s => s.addMessage)
  const clearChat = useStore(s => s.clearChat)
  

  const getDisplayName = (contactId) => {
    const c = contacts.find(x => x.id === contactId)
    return c?.name || contactId
  }

  const messages = useMemo(() => activeChatId ? (chats[activeChatId] || []) : [], [chats, activeChatId])

  if (!activeChatId) {
    return <div className="h-full flex items-center justify-center text-gray-500">Select a contact to view chat</div>
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="p-3 border-b flex items-center justify-between flex-shrink-0 bg-white">
        <div className="font-semibold truncate mr-2">{getDisplayName(activeChatId)}</div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <button 
            onClick={() => {
              if (window.confirm('Clear all messages for this conversation?')) {
                clearChat(activeChatId)
              }
            }}
            className="text-xs text-red-600 hover:text-red-800 px-2 py-1 border border-red-300 rounded hover:bg-red-50 transition-colors"
            title="Clear chat history"
          >
            Clear Chat
          </button>
          <label className="text-xs flex items-center gap-2">
            <span>Auto-Reply</span>
            <input type="checkbox" checked={autoReplyContacts[activeChatId] !== false} onChange={e=>setContactAutoReply(activeChatId, e.target.checked)} />
          </label>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto overflow-x-hidden p-3 space-y-2 bg-gray-50">
        {messages.map((m, idx) => (
          <div key={idx} className={`max-w-[80%] p-2 rounded ${m.sender==='me' ? 'bg-green-100 ml-auto' : 'bg-white'}`}>
            <div className="text-sm whitespace-pre-wrap break-words">{m.text}</div>
            <div className="text-[10px] text-gray-500">{new Date(m.timestamp).toLocaleString()}</div>
          </div>
        ))}
      </div>
      <div className="p-3 border-t flex gap-2 flex-shrink-0 bg-white">
        <input 
          className="flex-1 border rounded p-2 min-w-0" 
          value={input} 
          onChange={e=>setInput(e.target.value)} 
          placeholder="Type a manual reply..." 
          onKeyPress={e => {
            if (e.key === 'Enter') {
              e.preventDefault();
              const sendButton = e.target.parentElement.querySelector('button');
              sendButton?.click();
            }
          }}
        />
        <button className="bg-green-600 text-white px-4 rounded flex-shrink-0" onClick={async ()=>{
          const text = input.trim(); if (!text) return;
          setInput('');
          const ts = Date.now()
          addMessage(activeChatId, { sender: 'me', text, timestamp: ts })
          await api.sendMessage({ WHATSAPP_TOKEN: credentials.whatsappToken, PHONE_NUMBER_ID: credentials.phoneNumberId, to: activeChatId, text })
          await addMessageToVectorStore({ contactId: activeChatId, text, sender: credentials.phoneNumberId || 'me', receiver: activeChatId, timestamp: ts })
        }}>Send</button>
      </div>
    </div>
  )
}
