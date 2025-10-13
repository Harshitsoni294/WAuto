import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { MessageSquare, CheckSquare, Building2, Bot, Home } from 'lucide-react';

const Navbar = () => {
  const location = useLocation();
  
  const isActive = (path) => {
    if (path === '/app' && (location.pathname === '/app' || location.pathname === '/')) {
      return true;
    }
    return location.pathname === path;
  };

  const navItems = [
    { path: '/app', label: 'Dashboard', icon: Home },
    { path: '/business-description', label: 'Business', icon: Building2 }
  ];

  return (
    <nav className="bg-white shadow-lg border-b border-gray-200 fixed top-0 left-0 right-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          
          <div className="flex items-center">
            <Link to="/app" className="flex items-center space-x-3">
              <div>
                <h1 className="text-xl font-bold text-gray-900">WA Automation</h1>
                <p className="text-xs text-gray-500">WhatsApp Business AI</p>
              </div>
            </Link>
          </div>

          {/* Navigation Links */}
          <div className="hidden md:block">
            <div className="ml-10 flex items-baseline space-x-1">
              {navItems.map(({ path, label, icon: Icon }) => (
                <Link
                  key={path}
                  to={path}
                  className={`flex items-center px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                    isActive(path)
                      ? 'bg-blue-100 text-blue-700 shadow-sm'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  }`}
                >
                  <Icon className="w-4 h-4 mr-2" />
                  {label}
                </Link>
              ))}
            </div>
          </div>

          {/* AI Agent Indicator */}
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 px-3 py-2 bg-green-50 rounded-lg">
              <Bot className="w-4 h-4 text-green-600" />
              <span className="text-sm font-medium text-green-700">AI Agent Active</span>
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Navigation */}
      <div className="md:hidden">
        <div className="px-2 pt-2 pb-3 space-y-1 bg-white border-t border-gray-200">
          {navItems.map(({ path, label, icon: Icon }) => (
            <Link
              key={path}
              to={path}
              className={`flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                isActive(path)
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              }`}
            >
              <Icon className="w-4 h-4 mr-3" />
              {label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;