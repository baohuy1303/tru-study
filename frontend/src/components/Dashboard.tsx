import { useState } from 'react';
import Sidebar from './Sidebar';
import TasksSidebar from './TasksSidebar';
import ChatArea from './ChatArea';
import { PanelRightOpen, PanelRightClose, Trash2 } from 'lucide-react';
import api from '../lib/api';

export default function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [selectedTask, setSelectedTask] = useState<any>(null);
  const [tasksOpen, setTasksOpen] = useState(true);
  
  // Map of topic_id -> { id, title }
  const [checkedTopicsMap, setCheckedTopicsMap] = useState<Map<number, any>>(new Map());

  const handleTaskSelect = (course_id: any, task_id: any, type: string, course_name?: string) => {
    if (!course_id) {
      setSelectedTask(null);
      return;
    }
    setSelectedTask({ org_unit_id: course_id, task_id, type, course_name });
    setTasksOpen(false);
  };

  const handleTopicToggle = (topic: any, checked: boolean) => {
    setCheckedTopicsMap(prev => {
      const next = new Map(prev);
      if (checked) {
        next.set(topic.id, { id: topic.id, title: topic.title });
      } else {
        next.delete(topic.id);
      }
      return next;
    });
  };

  const selectedTopicsPayload = Array.from(checkedTopicsMap.values());

  const handleClearAllSessions = async () => {
    try {
      await api.delete('/sessions');
    } catch (err) {
      console.error("Failed to clear all sessions", err);
    }
    Object.keys(localStorage)
      .filter(k => k.startsWith('chat_'))
      .forEach(k => localStorage.removeItem(k));
  };

  return (
    <div className="flex h-screen bg-[#f4f3ec] text-[#08060d] dark:bg-[#16171d] dark:text-[#f3f4f6] overflow-hidden text-left font-sans max-w-none w-full border-none">
      
      {/* Left Sidebar: Course Navigation */}
      <aside className="w-80 shrink-0 border-r border-[#e5e4e7] dark:border-[#2e303a] bg-white dark:bg-[#1f2028] flex flex-col h-full shadow-[rgba(0,0,0,0.05)_2px_0_8px_-2px] z-20">
        <div className="p-4 border-b border-[#e5e4e7] dark:border-[#2e303a] flex items-center justify-between shrink-0">
          <h1 className="text-xl font-bold tracking-tight text-[#aa3bff] dark:text-[#c084fc] m-0">TruStudy</h1>
          <div className="flex items-center gap-2">
            <button
              onClick={handleClearAllSessions}
              className="p-1.5 hover:bg-rose-100 dark:hover:bg-rose-900/30 text-[#6b6375] hover:text-rose-500 dark:text-[#9ca3af] dark:hover:text-rose-400 rounded-lg transition-colors cursor-pointer"
              title="Clear all chat sessions"
            >
              <Trash2 size={16} strokeWidth={2.5} />
            </button>
            <button onClick={onLogout} className="text-sm font-medium text-[#6b6375] dark:text-[#9ca3af] hover:text-[#08060d] dark:hover:text-white transition-colors cursor-pointer text-right">
              Logout
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
          <Sidebar 
            selectedTask={selectedTask} 
            checkedTopics={new Set(checkedTopicsMap.keys())}
            onTopicToggle={handleTopicToggle}
          />
        </div>
      </aside>

      {/* Center: Main App Chat area */}
      <main className="flex-1 flex flex-col min-w-0 h-full overflow-hidden relative z-10">
        {/* Toggle button for right sidebar if closed */}
        {!tasksOpen && (
          <button 
            onClick={() => setTasksOpen(true)}
            className="absolute top-4 right-4 z-50 p-2.5 bg-white dark:bg-[#1f2028] border border-[#e5e4e7] dark:border-[#2e303a] rounded-xl shadow-md hover:bg-[#f4f3ec] dark:hover:bg-[#2e303a] transition-all"
            title="Open Tasks Sidebar"
          >
            <PanelRightOpen size={20} className="text-[#08060d] dark:text-[#f3f4f6]" />
          </button>
        )}
        <ChatArea 
          selectedTask={selectedTask} 
          onClearTask={() => setSelectedTask(null)}
          selectedTopics={selectedTopicsPayload}
        />
      </main>

      {/* Right Sidebar: Tasks & Workload */}
      <aside className={`shrink-0 border-l border-[#e5e4e7] dark:border-[#2e303a] bg-white dark:bg-[#1f2028] flex flex-col h-full shadow-[rgba(0,0,0,0.05)_-2px_0_8px_-2px] transition-all duration-300 ease-in-out z-20 ${tasksOpen ? 'w-96' : 'w-0 overflow-hidden border-none'}`}>
        <div className="p-4 border-b border-[#e5e4e7] dark:border-[#2e303a] shrink-0 flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight m-0 text-left whitespace-nowrap">Pending Tasks</h2>
          <button onClick={() => setTasksOpen(false)} className="p-1.5 hover:bg-[#f4f3ec] dark:hover:bg-[#2e303a] rounded-lg transition-colors">
            <PanelRightClose size={20} className="text-[#6b6375] dark:text-[#9ca3af]" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 bg-[#f4f3ec]/40 dark:bg-[#16171d]/40 custom-scrollbar whitespace-nowrap">
          <TasksSidebar selectedTask={selectedTask} onTaskSelect={handleTaskSelect} />
        </div>
      </aside>

    </div>
  );
}
