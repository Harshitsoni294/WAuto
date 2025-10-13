import axios from 'axios'

const SERVER_URL = import.meta.env.VITE_SERVER_URL || 'http://localhost:4000'

export const api = {
  sendMessage: async ({ WHATSAPP_TOKEN, PHONE_NUMBER_ID, to, text }) => {
    const { data } = await axios.post(`${SERVER_URL}/api/send-message`, { WHATSAPP_TOKEN, PHONE_NUMBER_ID, to, text })
    return data
  },
  geminiReply: async ({ prompt }) => {
    const { data } = await axios.post(`${SERVER_URL}/api/generate-gemini-reply`, { prompt })
    return data.text
  },
  embedding: async ({ text }) => {
    const { data } = await axios.post(`${SERVER_URL}/api/embedding`, { text })
    return data.embedding
  },
  createGoogleMeet: async ({ tokens, event }) => {
    const { data } = await axios.post(`${SERVER_URL}/api/create-google-meet`, { tokens, event })
    return data
  },
  mcpSend: async ({ WHATSAPP_TOKEN, PHONE_NUMBER_ID, aliases, command }) => {
    const { data } = await axios.post(`${SERVER_URL}/api/mcp/send`, { WHATSAPP_TOKEN, PHONE_NUMBER_ID, aliases, command })
    return data
  },


  // Todos removed

  // AI Agent
  aiAgentChat: async ({ message, context = {} }) => {
    const { data } = await axios.post(`${SERVER_URL}/api/ai-agent/chat`, { message, context })
    return data
  },
  aiAgentHistory: async () => {
    const { data } = await axios.get(`${SERVER_URL}/api/ai-agent/history`)
    return data
  },
  aiAgentClearHistory: async () => {
    const { data } = await axios.post(`${SERVER_URL}/api/ai-agent/clear-history`)
    return data
  }
}

export const socketServerUrl = SERVER_URL
