import React, { useMemo, useState } from 'react'
import { useStore } from '../store'
import { api } from '../lib/api'
import { addMessageToVectorStore, retrieveContext } from '../lib/rag'
import { v4 as uuidv4 } from 'uuid'
import { parseNaturalDateTime } from '../lib/time'

export default function ChatWindow() {
  const { activeChatId, chats, credentials, businessDescription, googleAuthTokens, addMessage, upsertContact } = useStore()
  const [input, setInput] = useState('')

  const messages = useMemo(() => activeChatId ? (chats[activeChatId] || []) : [], [chats, activeChatId])

  const sendWhatsApp = async (to, text) => {
    await api.sendMessage({ WHATSAPP_TOKEN: credentials.whatsappToken, PHONE_NUMBER_ID: credentials.phoneNumberId, to, text })
  }

  const handleSend = async () => {
    if (!activeChatId || !input.trim()) return
    const content = input.trim()
    setInput('')

    if (content.startsWith('/draft ')) {
      const topic = content.replace('/draft ', '').trim()
      const prompt = `You are a professional and helpful assistant. Help draft a concise, polite WhatsApp message about: "${topic}"`
      const reply = await api.geminiReply({ prompt })
      addMessage(activeChatId, { sender: 'me', text: reply, timestamp: Date.now() })
      await sendWhatsApp(activeChatId, reply)
      await addMessageToVectorStore({ contactId: activeChatId, text: reply })
      return
    }

    if (content.startsWith('/schedule ')) {
      // expected: /schedule meeting with {contact} at {time}
      try {
        const lower = content.toLowerCase()
        const atIndex = lower.indexOf(' at ')
        const timeStr = atIndex > -1 ? content.slice(atIndex + 4) : content.replace('/schedule','').trim()
        const taskTitle = atIndex > -1 ? content.slice(10, atIndex).trim() : 'Meeting'
        const start = parseNaturalDateTime(timeStr)
        const end = new Date(start.getTime() + 30*60*1000)

        const event = {
          summary: taskTitle,
          description: `Meeting with ${activeChatId}`,
          start: start.toISOString(),
          end: end.toISOString(),
          attendees: []
        }
  const { meetLink } = await api.createGoogleMeet({ tokens: googleAuthTokens, event })
  const invitePrompt = `Draft a professional invite for a meeting on ${start.toString()} with link ${meetLink}. Keep it short.`
        const msg = await api.geminiReply({ prompt: invitePrompt })
        addMessage(activeChatId, { sender: 'me', text: msg, timestamp: Date.now() })
        await sendWhatsApp(activeChatId, msg)
        await addMessageToVectorStore({ contactId: activeChatId, text: msg })
      } catch (e) {
        console.error('Schedule command failed', e)
      }
      return
    }

    // Regular message
    addMessage(activeChatId, { sender: 'me', text: content, timestamp: Date.now() })
    await sendWhatsApp(activeChatId, content)
    await addMessageToVectorStore({ contactId: activeChatId, text: content })
  }

  const handleAutoReply = async () => {
    if (!activeChatId) return
    const latest = messages[messages.length - 1]
    const contextDocs = await retrieveContext({ contactId: activeChatId, text: latest?.text || '' })
    const prompt = `You are a professional WhatsApp assistant for this business.\nBusiness: "${businessDescription}"\nRelevant past messages with this contact:\n${contextDocs.map(d=>`- ${d}`).join('\n')}\nThe client just wrote: "${latest?.text}"\n\nWrite a natural WhatsApp-style reply in 1–3 sentences (2–4 short lines max).\nCRITICAL OUTPUT RULES:\n- Output ONLY the message to send.\n- No prefaces, no options, no lists, no quotes, no markdown, no backticks.\n- Do not include labels like Option 1/2 or "Here is".\n- Friendly, concise, and professional.\nIf clarification is needed, ask one short question.`
    let reply = await api.geminiReply({ prompt })
    if (reply) {
      reply = reply.trim()
      reply = reply.replace(/^```[a-zA-Z]*\n?|```$/g, '').trim()
      if ((reply.startsWith('"') && reply.endsWith('"')) || (reply.startsWith("'") && reply.endsWith("'"))) {
        reply = reply.slice(1, -1).trim()
      }
    }
    addMessage(activeChatId, { sender: 'me', text: reply, timestamp: Date.now() })
    await sendWhatsApp(activeChatId, reply)
    await addMessageToVectorStore({ contactId: activeChatId, text: reply })
  }

  return (
    <div className="h-full flex flex-col">
      <div className="p-3 border-b font-semibold">{activeChatId || 'Select a contact'}</div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-gray-50">
        {messages.map((m, idx) => (
          <div key={idx} className={`max-w-[80%] p-2 rounded ${m.sender==='me' ? 'bg-green-100 ml-auto' : 'bg-white'}`}>
            <div className="text-sm whitespace-pre-wrap">{m.text}</div>
            <div className="text-[10px] text-gray-500">{new Date(m.timestamp).toLocaleString()}</div>
          </div>
        ))}
      </div>
      <div className="p-3 border-t flex gap-2">
        <input className="flex-1 border rounded p-2" value={input} onChange={e=>setInput(e.target.value)} placeholder="Type message or /draft, /schedule ..." />
        <button className="bg-green-600 text-white px-4 rounded" onClick={handleSend}>Send</button>
        <button className="bg-blue-600 text-white px-4 rounded" onClick={handleAutoReply}>Auto-Reply</button>
      </div>
    </div>
  )
}
