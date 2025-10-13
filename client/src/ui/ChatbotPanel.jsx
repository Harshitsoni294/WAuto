import React, { useState } from 'react'
import { useStore } from '../store'
import { api } from '../lib/api'
import { addMessageToVectorStore, retrieveContext } from '../lib/rag'
import { v4 as uuidv4 } from 'uuid'
import { parseNaturalDateTime } from '../lib/time'

export default function ChatbotPanel() {
  const { credentials, googleAuthTokens, businessDescription, addMessage, findContactByName } = useStore()
  const contacts = useStore(s => s.contacts)
  const [input, setInput] = useState('')
  const [log, setLog] = useState([])

  const logMsg = (m) => setLog((l)=>[m, ...l].slice(0,20))

  const sendWhatsApp = async (to, text) => {
    await api.sendMessage({ WHATSAPP_TOKEN: credentials.whatsappToken, PHONE_NUMBER_ID: credentials.phoneNumberId, to, text })
  }

  const handleSendTo = async (text, displayName) => {
    const aliasMap = {}
    for (const c of contacts) {
      if (c.name) aliasMap[(c.name||'').toLowerCase()] = c.id
      aliasMap[(c.id||'').toLowerCase()] = c.id
    }
    const command = `send "${text}" to ${displayName}`
    await api.mcpSend({ WHATSAPP_TOKEN: credentials.whatsappToken, PHONE_NUMBER_ID: credentials.phoneNumberId, aliases: aliasMap, command })
  const contact = findContactByName(displayName)
  const to = contact?.id || displayName
  const ts = Date.now()
  addMessage(to, { sender: 'me', text, timestamp: ts })
  await addMessageToVectorStore({ contactId: to, text, sender: credentials.phoneNumberId || 'me', receiver: to, timestamp: ts })
  }

  const handleCommand = async (raw) => {
    const content = raw.trim()
    if (!content) return

    // Natural language: send|sent with optional quotes
    let m = content.match(/^(send|sent)\s+"([\s\S]+?)"\s+to\s+(.+)$/i)
    if (!m) m = content.match(/^(send|sent)\s+'([\s\S]+?)'\s+to\s+(.+)$/i)
    if (!m) m = content.match(/^(send|sent)\s+(.+?)\s+to\s+(.+)$/i)
    if (m) {
      const text = m[2]
      const name = m[3]
      try {
        await handleSendTo(text, name)
        logMsg(`Sent to ${name}`)
      } catch (e) {
        logMsg(`Send error: ${e?.response?.data?.error || e.message}`)
      }
      return
    }

    if (content.startsWith('/draft ')) {
      const topic = content.replace('/draft ', '').trim()
      const prompt = `You are a professional and helpful assistant. Help draft a concise, polite WhatsApp message about: "${topic}"`
      const reply = await api.geminiReply({ prompt })
      logMsg('Draft ready. Use: send "<text>" to <Name>')
      setInput(reply)
      return
    }

    if (content.startsWith('/schedule ')) {
      // /schedule meeting with {name} at {time}
      const lower = content.toLowerCase()
      const atIndex = lower.indexOf(' at ')
      const toIndex = lower.indexOf(' with ')
      const timeStr = atIndex > -1 ? content.slice(atIndex + 4) : content
      const name = toIndex > -1 && atIndex > -1 ? content.slice(toIndex + 6, atIndex).trim() : null
      const taskTitle = 'Meeting'
      const start = parseNaturalDateTime(timeStr)
      const end = new Date(start.getTime() + 30*60*1000)

      const { meetLink } = await api.createGoogleMeet({ tokens: googleAuthTokens, event: {
        summary: taskTitle,
        description: name ? `Meeting with ${name}` : 'Meeting',
        start: start.toISOString(),
        end: end.toISOString(),
        attendees: []
      } })

  // Todo feature removed; skip adding todo

      const msg = await api.geminiReply({ prompt: `Draft a professional invite for a meeting on ${start.toString()} with link ${meetLink}. Keep it short.` })

      if (name) {
        await handleSendTo(msg, name)
        logMsg(`Invite sent to ${name}`)
      } else {
        setInput(msg)
        logMsg('Invite drafted. Use: send "<text>" to <Name>')
      }
      return
    }

    logMsg('Unknown command. Try: send "Hello" to Alice')
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="p-3 border-b font-semibold flex-shrink-0 bg-white">Chatbot</div>
      <div className="p-3 border-b text-xs text-gray-600 space-y-1 flex-shrink-0 bg-gray-50">
        <div>Examples:</div>
        <div>- send "hello from developer" to Harshit Soni</div>
        <div>- /draft product update</div>
        <div>- /schedule meeting with Harshit Soni at tomorrow 5pm</div>
      </div>
      <div className="flex-1 p-3 space-y-2 overflow-y-auto overflow-x-hidden">
        {log.length === 0 && (
          <div className="text-gray-500 text-sm italic">Command output will appear here...</div>
        )}
        {log.map((l,i)=>(<div key={i} className="text-xs text-gray-700 break-words">• {l}</div>))}
      </div>
      <div className="p-3 border-t flex gap-2 flex-shrink-0 bg-white">
        <input 
          className="flex-1 border rounded p-2 min-w-0" 
          placeholder="Type command..." 
          value={input} 
          onChange={e=>setInput(e.target.value)} 
          onKeyPress={e => {
            if (e.key === 'Enter') {
              e.preventDefault();
              handleCommand(input);
              setInput('');
            }
          }}
        />
        <button 
          className="bg-indigo-600 text-white px-4 rounded flex-shrink-0" 
          onClick={()=>{
            handleCommand(input);
            setInput('');
          }}
        >
          Run
        </button>
      </div>
    </div>
  )
}
