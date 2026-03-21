import Sidebar from './Sidebar';
import TasksSidebar from './TasksSidebar';
import ChatArea from './ChatArea';

export default function Dashboard({ onLogout }: { onLogout: () => void }) {
  return (
    <div className="flex h-screen bg-[#f4f3ec] text-[#08060d] dark:bg-[#16171d] dark:text-[#f3f4f6] overflow-hidden text-left font-sans max-w-none w-full border-none">
      
      {/* Left Sidebar: Course Navigation */}
      <aside className="w-80 shrink-0 border-r border-[#e5e4e7] dark:border-[#2e303a] bg-white dark:bg-[#1f2028] flex flex-col h-full shadow-[rgba(0,0,0,0.05)_2px_0_8px_-2px]">
        <div className="p-4 border-b border-[#e5e4e7] dark:border-[#2e303a] flex items-center justify-between shrink-0">
          <h1 className="text-xl font-bold tracking-tight text-[#aa3bff] dark:text-[#c084fc] m-0">TruStudy</h1>
          <button onClick={onLogout} className="text-sm font-medium text-[#6b6375] dark:text-[#9ca3af] hover:text-[#08060d] dark:hover:text-white transition-colors cursor-pointer text-right">
            Logout
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
          <Sidebar />
        </div>
      </aside>

      {/* Center: Main App Chat area */}
      <main className="flex-1 flex flex-col justify-end min-w-0 h-full overflow-hidden">
        <ChatArea />
      </main>

      {/* Right Sidebar: Tasks & Workload */}
      <aside className="w-96 shrink-0 border-l border-[#e5e4e7] dark:border-[#2e303a] bg-white dark:bg-[#1f2028] flex flex-col h-full shadow-[rgba(0,0,0,0.05)_-2px_0_8px_-2px]">
        <div className="p-4 border-b border-[#e5e4e7] dark:border-[#2e303a] shrink-0">
          <h2 className="text-lg font-semibold tracking-tight m-0 text-left">Pending Tasks</h2>
        </div>
        <div className="flex-1 overflow-y-auto p-4 bg-[#f4f3ec]/40 dark:bg-[#16171d]/40 custom-scrollbar">
          <TasksSidebar />
        </div>
      </aside>

    </div>
  );
}
