import React, { useState } from 'react'
import { useStore } from '../store'
import Navbar from '../components/Navbar'
import { Save, Building2 } from 'lucide-react'

export default function BusinessDescription() {
  const current = useStore(s => s.businessDescription)
  const setBusinessDescription = useStore(s => s.setBusinessDescription)
  const [val, setVal] = useState(current || '')
  const [saved, setSaved] = useState(false)

  const handleSave = () => {
    setBusinessDescription(val)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Fixed Navbar */}
      <Navbar />
      
      {/* Main content with padding for fixed navbar */}
      <div className="pt-20 pb-6 px-6">
        <div className="max-w-3xl mx-auto bg-white p-6 rounded-lg shadow-lg space-y-6">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <Building2 className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Business Description</h1>
              <p className="text-gray-600">Describe your business to help the AI assistant understand your context</p>
            </div>
          </div>
          
          <div className="space-y-4">
            <textarea 
              className="w-full border border-gray-300 rounded-lg p-4 h-64 text-gray-900 placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none" 
              value={val} 
              onChange={e => setVal(e.target.value)} 
              placeholder="Describe your business, products, services, target audience, and any other relevant information that will help the AI assistant provide better responses..."
            />
            
            <div className="flex items-center justify-between">
              <p className="text-sm text-gray-500">
                Characters: {val.length}
              </p>
              
              <button 
                className={`flex items-center gap-2 px-6 py-2 rounded-lg font-medium transition-all duration-200 ${
                  saved 
                    ? 'bg-green-600 text-white' 
                    : 'bg-blue-600 hover:bg-blue-700 text-white hover:shadow-md'
                }`}
                onClick={handleSave}
                disabled={saved}
              >
                <Save className="w-4 h-4" />
                {saved ? 'Saved!' : 'Save Description'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
