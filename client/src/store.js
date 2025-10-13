import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useStore = create(persist((set, get) => ({
  credentials: null,
  contacts: [],
  chats: {},
  businessDescription: '',
  googleAuthTokens: null,
  activeChatId: null,
  autoReplyEnabled: true,
  autoReplyContacts: {},

  setCredentials: (creds) => set({ credentials: creds }),
  setBusinessDescription: (desc) => set({ businessDescription: desc }),
  setActiveChatId: (id) => set({ activeChatId: id }),
  setAutoReplyEnabled: (v) => set({ autoReplyEnabled: v }),
  setContactAutoReply: (id, enabled) => set((state) => ({ autoReplyContacts: { ...state.autoReplyContacts, [id]: enabled } })),
  setGoogleTokens: (tokens) => set({ googleAuthTokens: tokens }),

  upsertContact: (id, data) => set((state) => {
    const existing = state.contacts.find(c => c.id === id)
    const updated = { id, ...(existing || {}), ...data }
    const contacts = existing ? state.contacts.map(c => c.id === id ? updated : c) : [updated, ...state.contacts]
    return { contacts }
  }),

  addMessage: (contactId, msg) => set((state) => {
    const chat = state.chats[contactId] || []
    const chats = { ...state.chats, [contactId]: [...chat, msg] }
    return { chats }
  }),

  clearChat: (contactId) => set((state) => {
    const chats = { ...state.chats }
    delete chats[contactId]
    return { chats }
  }),

  findContactByName: (name) => {
    const state = get()
    const lower = (name || '').trim().toLowerCase()
    return state.contacts.find(c => (c.name || '').toLowerCase() === lower || (c.id || '').toLowerCase() === lower)
  },

  findContactByFuzzyName: (name) => {
    const state = get()
    const q = (name || '').trim().toLowerCase().replace(/\s+/g,' ')
    if (!q) return undefined
    // Exact first
    let found = state.contacts.find(c => (c.name||'').toLowerCase() === q || (c.id||'').toLowerCase() === q)
    if (found) return found
    // By includes
    found = state.contacts.find(c => (c.name||'').toLowerCase().includes(q) || (c.id||'').toLowerCase().includes(q))
    if (found) return found
    // By tokens (all tokens must appear)
    const tokens = q.split(' ').filter(Boolean)
    found = state.contacts.find(c => {
      const hay = `${c.name||''} ${c.id||''}`.toLowerCase()
      return tokens.every(t => hay.includes(t))
    })
    return found
  },

}), { name: 'wa-automation-store' }))
