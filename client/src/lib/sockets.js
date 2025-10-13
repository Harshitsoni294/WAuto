import { io } from 'socket.io-client'
import { socketServerUrl } from './api'
import { useStore } from '../store'

let socket

export function getSocket() {
  if (!socket) {
    const creds = useStore.getState().credentials
    const url = creds?.serverUrl || socketServerUrl
    socket = io(url, { transports: ['websocket'] })
    // Expose globally for components that check window.socket
    if (typeof window !== 'undefined') {
      window.socket = socket
    }
  }
  return socket
}
