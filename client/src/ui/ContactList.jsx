import React, { useMemo, useState } from 'react'
import { useStore } from '../store'

export default function ContactList() {
  const contacts = useStore(s => s.contacts)
  const setActiveChatId = useStore(s => s.setActiveChatId)
  const upsertContact = useStore(s => s.upsertContact)
  const [renameId, setRenameId] = useState(null)
  const [newName, setNewName] = useState('')
  const [loading, setLoading] = useState(false)


  const ordered = useMemo(() => [...contacts].sort((a,b)=> (b.timestamp||0) - (a.timestamp||0)), [contacts])

  const submitRename = async () => {
    if (renameId && newName.trim()) {
      setLoading(true)
      try {
        // Update the store for immediate UI update (client-side only)
        upsertContact(renameId, { name: newName.trim() })
        setRenameId(null)
        setNewName('')
      } catch (error) {
        console.error('Failed to rename contact:', error)
        alert('Failed to rename contact. Please try again.')
      } finally {
        setLoading(false)
      }
    }
  }

  const getDisplayName = (contact) => {
    return contact.name || contact.id
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="p-3 border-b font-semibold flex-shrink-0 bg-white">Contacts</div>
      <div className="flex-1 overflow-y-auto overflow-x-hidden">
        {ordered.map(c => (
          <div key={c.id} className="p-3 border-b hover:bg-gray-50 cursor-pointer" onClick={()=>setActiveChatId(c.id)}>
            <div className="flex items-center justify-between">
              <div className="font-medium truncate mr-2">{getDisplayName(c)}</div>
              <button className="text-xs text-blue-600 flex-shrink-0" onClick={(e)=>{ e.stopPropagation(); setRenameId(c.id); setNewName(getDisplayName(c)); }}>Rename</button>
            </div>
            <div className="text-sm text-gray-600 truncate">{c.lastMessage}</div>
          </div>
        ))}
      </div>

      {renameId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white p-4 rounded shadow w-80 space-y-3">
            <div className="font-semibold">Rename Contact</div>
            <input value={newName} onChange={e=>setNewName(e.target.value)} className="w-full border rounded p-2" />
            <div className="flex gap-2 justify-end">
              <button className="px-3 py-1" onClick={()=>setRenameId(null)} disabled={loading}>Cancel</button>
              <button className="bg-blue-600 text-white px-3 py-1 rounded disabled:opacity-50" onClick={submitRename} disabled={loading || !newName.trim()}>
                {loading ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
