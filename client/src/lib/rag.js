import { v4 as uuidv4 } from 'uuid'
import { api } from './api'

const KEY = 'wa_vectors_v1'

function loadStore() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || []
  } catch {
    return []
  }
}

function saveStore(items) {
  localStorage.setItem(KEY, JSON.stringify(items))
}

function cosine(a, b) {
  let dot = 0, na = 0, nb = 0
  const len = Math.min(a.length, b.length)
  for (let i=0; i<len; i++) { dot += a[i]*b[i]; na += a[i]*a[i]; nb += b[i]*b[i] }
  if (!na || !nb) return 0
  return dot / (Math.sqrt(na) * Math.sqrt(nb))
}

export async function addMessageToVectorStore({ contactId, text, sender, receiver, timestamp }) {
  const items = loadStore()
  const embedding = await api.embedding({ text })
  const id = uuidv4()
  const ts = typeof timestamp === 'number' ? timestamp : Date.now()
  items.push({ id, contact_id: contactId, embedding, text, sender: sender || null, receiver: receiver || null, ts })
  saveStore(items)
  return id
}

export async function retrieveContext({ contactId, text, nResults = 5 }) {
  const items = loadStore().filter(i => i.contact_id === contactId)
  if (items.length === 0) return []
  const queryEmbedding = await api.embedding({ text })
  const scored = items.map(i => ({ doc: i.text, score: cosine(queryEmbedding, i.embedding) }))
  scored.sort((a,b)=> b.score - a.score)
  return scored.slice(0, nResults).map(s => s.doc)
}

export function getAllVectors() {
  return loadStore()
}

export function clearVectors() {
  saveStore([])
}
