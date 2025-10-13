import React, { useState, useEffect, useRef } from 'react';
import { Send, Trash2, MessageSquare, User, Bot, Calendar, CheckCircle2, Clock } from 'lucide-react';
import { api } from '../lib/api';
import { useStore } from '../store';

const AIAgentChat = () => {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const messagesEndRef = useRef(null);
  const credentials = useStore(s => s.credentials);
  const contacts = useStore(s => s.contacts);
  const googleTokens = useStore(s => s.googleAuthTokens);
  const addMessage = useStore(s => s.addMessage);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Load conversation history when component mounts
    loadConversationHistory();
    
    // Set up socket connection if available
    if (window.socket) {
      setIsConnected(true);
      
      // Listen for AI agent responses
      window.socket.on('ai_agent_response', (data) => {
        handleAgentResponse(data.result);
      });
      
      // Listen for history cleared event
      window.socket.on('ai_agent_history_cleared', () => {
        setMessages([]);
      });
      
      return () => {
        window.socket.off('ai_agent_response');
        window.socket.off('ai_agent_history_cleared');
      };
    }
  }, []);

  const loadConversationHistory = async () => {
    try {
      const data = await api.aiAgentHistory();
      
      if (data.success && data.history) {
        const formattedMessages = data.history.map((msg, index) => ({
          id: index,
          role: msg.role,
          content: msg.message,
          timestamp: msg.timestamp,
          actionType: msg.action_type,
          details: msg.details
        }));
        setMessages(formattedMessages);
      }
    } catch (error) {
      console.error('Error loading conversation history:', error);
    }
  };

  const handleAgentResponse = (result) => {
    const responseMessage = {
      id: Date.now(),
      role: 'agent',
      content: result.response,
      timestamp: new Date().toISOString(),
      actionType: result.action_type,
      details: result.details,
      success: result.success
    };
    
    setMessages(prev => [...prev, responseMessage]);
    setIsLoading(false);

    // If this was a successful send_message, add it to the chat
    if (result.action_type === 'send_message' && result.success && result.details) {
      const recipientPhone = result.details.recipient_phone;
      const message = result.details.message;
      
      if (recipientPhone && message) {
        // Add the sent message to the chat with the recipient
        addMessage(recipientPhone, {
          sender: 'me',
          text: message,
          timestamp: Date.now()
        });
      }
    }

    // If this was a successful schedule_meeting, reflect the same invite in the contact chat
    if (result.action_type === 'schedule_meeting' && result.success && result.details) {
      const details = result.details || {};
      const invite = details.invite_message;
      let recipient = details.recipient_phone; // could be phone or name alias

      if (invite && recipient) {
        // Normalize: if recipient is a known contact alias by name, map it to its id
        // contacts in store have ids; we try to find an exact id match or name match
        const found = contacts.find(c => c.id === recipient || (c.name||'').toLowerCase() === (recipient||'').toLowerCase());
        const contactId = found ? found.id : recipient;

        addMessage(contactId, {
          sender: 'me',
          text: invite,
          timestamp: Date.now()
        });
      }
    }
  };

  const sendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // Build aliases for the agent: name->id and id->id
      const aliases = {};
      for (const c of contacts) {
        if (c?.name) aliases[(c.name||'').toLowerCase()] = c.id;
        if (c?.id) aliases[(c.id||'').toLowerCase()] = c.id;
      }
      const context = {
        whatsapp: {
          token: credentials?.whatsappToken,
          phone_number_id: credentials?.phoneNumberId,
        },
        aliases,
        contacts: contacts.map(c => ({ id: c.id, name: c.name })),
        google_tokens: googleTokens || undefined,
      };
      const result = await api.aiAgentChat({ message: inputMessage, context });
      
      if (!window.socket) {
        // If no socket connection, handle response directly
        handleAgentResponse(result);
      }
      
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = {
        id: Date.now(),
        role: 'agent',
        content: 'Sorry, I encountered an error. Please try again.',
        timestamp: new Date().toISOString(),
        actionType: 'error',
        success: false
      };
      setMessages(prev => [...prev, errorMessage]);
      setIsLoading(false);
    }

    setInputMessage('');
  };

  const clearHistory = async () => {
    try {
      const result = await api.aiAgentClearHistory();
      
      if (result.success) {
        setMessages([]);
      }
    } catch (error) {
      console.error('Error clearing history:', error);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  const getActionIcon = (actionType) => {
    switch (actionType) {
      case 'send_message':
        return <Send className="w-4 h-4 text-blue-500" />;
      case 'schedule_meeting':
        return <Calendar className="w-4 h-4 text-green-500" />;
      // add_todo removed
      case 'general_chat':
        return <MessageSquare className="w-4 h-4 text-gray-500" />;
      case 'error':
        return <Clock className="w-4 h-4 text-red-500" />;
      default:
        return null;
    }
  };

  const getActionBadge = (actionType, success) => {
    if (!actionType) return null;
    
    const colors = {
      send_message: success ? 'bg-blue-100 text-blue-800' : 'bg-red-100 text-red-800',
      schedule_meeting: success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800',
  // add_todo removed
      general_chat: 'bg-gray-100 text-gray-800',
      error: 'bg-red-100 text-red-800'
    };

    const labels = {
      send_message: 'Message Sent',
      schedule_meeting: 'Meeting Scheduled',
  // add_todo removed
      general_chat: 'Chat',
      error: 'Error'
    };

    return (
      <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${colors[actionType] || 'bg-gray-100 text-gray-800'}`}>
        {getActionIcon(actionType)}
        {labels[actionType] || actionType}
      </span>
    );
  };

  const renderMessageDetails = (details, actionType) => {
    if (!details || typeof details !== 'object') return null;

    switch (actionType) {
      case 'send_message':
        return (
          <div className="mt-2 p-2 bg-blue-50 rounded-lg text-sm">
            <p><strong>Recipient:</strong> {details.recipient}</p>
            <p><strong>Message:</strong> {details.message}</p>
          </div>
        );
      
      case 'schedule_meeting':
        const meetingInfo = details.meeting_info || {};
        return (
          <div className="mt-2 p-2 bg-green-50 rounded-lg text-sm">
            <p><strong>Contact:</strong> {meetingInfo.contact_name}</p>
            <p><strong>Date:</strong> {meetingInfo.date}</p>
            <p><strong>Time:</strong> {meetingInfo.time}</p>
            {details.meeting_result?.meet_link && (
              <p><strong>Meeting Link:</strong> 
                <a href={details.meeting_result.meet_link} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline ml-1">
                  Join Meeting
                </a>
              </p>
            )}
          </div>
        );
      
      // 'add_todo' case removed (feature deprecated)
      
      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-white">
        <div className="flex items-center gap-3">
          <Bot className="w-8 h-8 text-blue-600" />
          <div>
            <h2 className="text-xl font-semibold text-gray-900">AI Agent</h2>
            <p className="text-sm text-gray-500">
              {isConnected ? 'Connected' : 'Offline'} • Send messages and schedule meetings
            </p>
          </div>
        </div>
        <button
          onClick={clearHistory}
          className="flex items-center gap-2 px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
        >
          <Trash2 className="w-4 h-4" />
          Clear Chat
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="text-center py-8">
            <Bot className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Welcome to AI Agent</h3>
            <p className="text-gray-500 mb-4">I can help you with:</p>
            <div className="text-sm text-gray-600 space-y-1">
              <p>• Send messages to contacts</p>
              <p>• Schedule meetings with Google Meet</p>
              {/* Todo feature removed */}
              <p>• Answer questions about the system</p>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {message.role === 'agent' && (
                <div className="flex-shrink-0">
                  <Bot className="w-8 h-8 text-blue-600" />
                </div>
              )}
              
              <div className={`max-w-[70%] ${message.role === 'user' ? 'order-1' : ''}`}>
                <div
                  className={`rounded-lg p-3 ${
                    message.role === 'user'
                      ? 'bg-blue-600 text-white'
                      : message.success === false
                      ? 'bg-red-50 text-red-900 border border-red-200'
                      : 'bg-gray-100 text-gray-900'
                  }`}
                >
                  <div className="whitespace-pre-wrap">{message.content}</div>
                  
                  {message.actionType && message.role === 'agent' && (
                    <div className="mt-2">
                      {getActionBadge(message.actionType, message.success)}
                    </div>
                  )}
                  
                  {renderMessageDetails(message.details, message.actionType)}
                </div>
                
                <div className="text-xs text-gray-500 mt-1 px-1">
                  {formatTimestamp(message.timestamp)}
                </div>
              </div>
              
              {message.role === 'user' && (
                <div className="flex-shrink-0">
                  <User className="w-8 h-8 text-gray-600" />
                </div>
              )}
            </div>
          ))
        )}
        
        {isLoading && (
          <div className="flex gap-3 justify-start">
            <Bot className="w-8 h-8 text-blue-600" />
            <div className="bg-gray-100 rounded-lg p-3">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-200 bg-white">
        <div className="flex gap-2">
          <textarea
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask me to send messages, schedule meetings, or just chat..."
            className="flex-1 resize-none border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            rows="2"
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={isLoading || !inputMessage.trim()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            <Send className="w-4 h-4" />
            Send
          </button>
        </div>
        
        <div className="mt-2 text-xs text-gray-500">
          Examples: "Send hello to John", "Schedule meeting with Sarah tomorrow at 3pm"
        </div>
      </div>
    </div>
  );
};

export default AIAgentChat;