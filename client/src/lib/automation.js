import { useStore } from '../store'
import { addMessageToVectorStore } from './rag'
import { api } from './api'

export async function handleWebhookPayload(payload) {
  try {
    const entry = payload.entry?.[0]
    const change = entry?.changes?.[0]
    const value = change?.value
    const messages = value?.messages
    const contacts = value?.contacts
    const fromMsg = messages?.[0]
    if (!fromMsg) return

    const from = fromMsg.from
    const text = fromMsg.text?.body || fromMsg.button?.text || '[non-text message]'
    const timestamp = Number(fromMsg.timestamp) * 1000 || Date.now()

    // Try to get contact name from webhook (client-side only; no server alias lookup)
    let contactName = from
    if (contacts?.[0]?.profile?.name) {
      contactName = contacts[0].profile.name
    }

    const store = useStore.getState()
    store.upsertContact(from, { id: from, name: contactName, lastMessage: text, timestamp })
    store.addMessage(from, { sender: 'them', text, timestamp })
    store.setActiveChatId(from)

  // Persist incoming message with full metadata
  const creds = store.credentials
  await addMessageToVectorStore({ contactId: from, text, sender: from, receiver: creds?.phoneNumberId || 'me', timestamp })

  // Auto-reply gating
  if (!store.autoReplyEnabled) return
  const perContact = store.autoReplyContacts[from]
  if (perContact === false) return

  // Build full conversation context (last 50)
  const history = (store.chats[from] || []).slice(-50)
  const convo = history
    .map(m => `${m.sender === 'me' ? 'ME' : 'THEM'} [${new Date(m.timestamp).toLocaleString()}]: ${m.text}`)
    .join('\n')
  const business = store.businessDescription || ''
  const prompt = `You are a professional WhatsApp assistant for this business.\nBusiness: "${business}"\nConversation history with this contact (oldest to newest):\n${convo}\nThe client just wrote: "${text}"\n\nWrite a natural WhatsApp-style reply in 1–3 sentences (2–4 short lines max).\nCRITICAL OUTPUT RULES:\n- Output ONLY the message to send.\n- No prefaces, no options, no lists, no quotes, no markdown, no backticks.\n- Do not include labels like Option 1/2 or "Here is".\n- Friendly, concise, and professional.\nIf clarification is needed, ask one short question.`
  let reply
  try {
    reply = await api.geminiReply({ prompt })
    // light normalization: strip code fences and surrounding quotes
    if (reply) {
      reply = reply.trim()
      reply = reply.replace(/^```[a-zA-Z]*\n?|```$/g, '').trim()
      if ((reply.startsWith('"') && reply.endsWith('"')) || (reply.startsWith("'") && reply.endsWith("'"))) {
        reply = reply.slice(1, -1).trim()
      }
    }
  } catch (e) {
    console.error('Gemini failed, using fallback reply:', e?.response?.data || e.message)
    reply = 'Thanks for your message. We\'ll get back to you shortly.'
  }

  if (!creds) return
  // Build alias map for MCP send
  const aliasMap = {}
  for (const c of store.contacts) {
    if (c.name) aliasMap[(c.name||'').toLowerCase()] = c.id
    aliasMap[(c.id||'').toLowerCase()] = c.id
  }
  const targetDisplay = (store.contacts.find(c=>c.id===from)?.name) || from
  const command = `send "${reply}" to ${targetDisplay}`
  try {
    await api.mcpSend({ WHATSAPP_TOKEN: creds.whatsappToken, PHONE_NUMBER_ID: creds.phoneNumberId, aliases: aliasMap, command })
  } catch (e) {
    console.error('Auto-reply MCP send failed:', e?.response?.data || e.message)
    return
  }
  const now = Date.now()
  store.addMessage(from, { sender: 'me', text: reply, timestamp: now })
  await addMessageToVectorStore({ contactId: from, text: reply, sender: creds.phoneNumberId || 'me', receiver: from, timestamp: now })
  } catch (e) {
    console.error('automation handleWebhookPayload error', e)
  }
}
