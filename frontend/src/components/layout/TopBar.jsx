import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { Avatar, AvatarFallback } from '../ui/avatar';
import { Bell } from 'lucide-react';

export const TopBar = ({ title, subtitle }) => {
  const { user } = useAuth();
  
  const initials = user?.name
    ? user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : 'U';

  return (
    <header className="h-16 bg-white border-b border-slate-100 flex items-center justify-between px-8" data-testid="topbar">
      <div>
        <h1 className="font-heading font-semibold text-xl text-slate-900">{title}</h1>
        {subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}
      </div>
      
      <div className="flex items-center gap-4">
        <button 
          className="p-2 rounded-full hover:bg-slate-100 transition-colors relative"
          data-testid="notifications-btn"
        >
          <Bell className="w-5 h-5 text-slate-600" />
        </button>
        
        <div className="flex items-center gap-3">
          <Avatar className="h-9 w-9">
            <AvatarFallback className="bg-indigo-100 text-indigo-600 text-sm font-medium">
              {initials}
            </AvatarFallback>
          </Avatar>
          <div className="hidden sm:block">
            <p className="text-sm font-medium text-slate-900">{user?.name}</p>
            <p className="text-xs text-slate-500">{user?.email}</p>
          </div>
        </div>
      </div>
    </header>
  );
};
