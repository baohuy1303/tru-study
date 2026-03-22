import { useState, useEffect, useRef, useCallback } from 'react';
import Sidebar from './Sidebar';
import TasksSidebar from './TasksSidebar';
import ChatArea from './ChatArea';
import { PanelRightOpen, PanelRightClose, Trash2, AlertTriangle, Database, CalendarPlus, Loader2 } from 'lucide-react';
import { SignInButton, SignedIn, SignedOut, UserButton, useSession } from '@clerk/clerk-react';
import api from '../lib/api';

interface TodoItem {
  id: string;
  text: string;
  completed: boolean;
  order: number;
}

export default function Dashboard({ onLogout }: { onLogout: () => void }) {
  const [selectedTask, setSelectedTask] = useState<any>(null);
  const [tasksOpen, setTasksOpen] = useState(true);
  const [resetKey, setResetKey] = useState(0);
  const [clearDataModal, setClearDataModal] = useState<'none' | 'chats' | 'storage'>('none');
  const [isAddAllModalOpen, setIsAddAllModalOpen] = useState(false);
  const [addingAllLoading, setAddingAllLoading] = useState(false);
  const { session } = useSession();

  // Map of session_id -> TodoItem[] for AI-generated to-do lists
  const [todoPlans, setTodoPlans] = useState<Map<string, TodoItem[]>>(new Map());
  const patchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Map of task_id -> uploaded file for link-only assignment main file persistence
  const [assignmentUploadsMap, setAssignmentUploadsMap] = useState<Map<number, any>>(new Map());

  // Load persisted assignment uploads on mount
  useEffect(() => {
    const map = new Map<number, any>();
    Object.keys(localStorage)
      .filter(k => k.startsWith('assignment_upload_'))
      .forEach(k => {
        const id = parseInt(k.replace('assignment_upload_', ''));
        if (!isNaN(id)) {
          try { map.set(id, JSON.parse(localStorage.getItem(k)!)); } catch {}
        }
      });
    if (map.size > 0) setAssignmentUploadsMap(map);
  }, []);

  const handleAssignmentFileUploaded = useCallback((taskId: number, uploadData: any) => {
    setAssignmentUploadsMap(prev => {
      const next = new Map(prev);
      next.set(taskId, uploadData);
      return next;
    });
    localStorage.setItem(`assignment_upload_${taskId}`, JSON.stringify(uploadData));
  }, []);

  // Map of topic_id -> { id, title, path?, file_name? }
  const [checkedTopicsMap, setCheckedTopicsMap] = useState<Map<number, any>>(new Map());

  // Map of topic_id -> upload metadata for link topics replaced with local files
  const [replacedLinksMap, setReplacedLinksMap] = useState<Map<number, any>>(new Map());

  // Load persisted link replacements on mount
  useEffect(() => {
    const map = new Map<number, any>();
    Object.keys(localStorage)
      .filter(k => k.startsWith('link_topic_'))
      .forEach(k => {
        const id = parseInt(k.replace('link_topic_', ''));
        if (!isNaN(id)) {
          try { map.set(id, JSON.parse(localStorage.getItem(k)!)); } catch {}
        }
      });
    if (map.size > 0) setReplacedLinksMap(map);
  }, []);

  const handleTaskSelect = (course_id: any, task_id: any, type: string, course_name?: string) => {
    setCheckedTopicsMap(new Map());
    
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
        // Include path/file_name if present (for replaced link topics)
        const entry: any = { id: topic.id, title: topic.title };
        if (topic.path) entry.path = topic.path;
        if (topic.file_name) entry.file_name = topic.file_name;
        if (topic.orgUnitId) entry.orgUnitId = topic.orgUnitId;
        next.set(topic.id, entry);
      } else {
        next.delete(topic.id);
      }
      return next;
    });
  };

  const handleLinkTopicReplaced = (topicId: number, topicTitle: string, uploadData: any) => {
    // Save replacement to state
    setReplacedLinksMap(prev => {
      const next = new Map(prev);
      next.set(topicId, uploadData);
      return next;
    });
    // Persist to localStorage
    localStorage.setItem(`link_topic_${topicId}`, JSON.stringify(uploadData));

    // Auto-select the replaced topic for RAG
    setCheckedTopicsMap(prev => {
      const next = new Map(prev);
      next.set(topicId, { id: topicId, title: topicTitle, path: uploadData.path, file_name: uploadData.file_name });
      return next;
    });
  };

  const selectedTopicsPayload = Array.from(checkedTopicsMap.values());

  // Receive task plan from pipeline SSE result
  const handleTaskPlanReceived = useCallback((sessionId: string, plan: TodoItem[]) => {
    setTodoPlans(prev => {
      const next = new Map(prev);
      next.set(sessionId, plan);
      return next;
    });
  }, []);

  // Update todos (optimistic + debounced PATCH)
  const handleTodosChange = useCallback((sessionId: string, todos: TodoItem[]) => {
    setTodoPlans(prev => {
      const next = new Map(prev);
      next.set(sessionId, todos);
      return next;
    });
    if (patchTimerRef.current) clearTimeout(patchTimerRef.current);
    patchTimerRef.current = setTimeout(() => {
      api.patch(`/sessions/${sessionId}/todos`, { todos }).catch(err =>
        console.error("Failed to update todos", err)
      );
    }, 400);
  }, []);

  // Fetch existing todos when a task is selected
  useEffect(() => {
    if (selectedTask?.task_id && selectedTask.type === 'assignment') {
      const sid = `${selectedTask.org_unit_id}_${selectedTask.task_id}`;
      if (!todoPlans.has(sid)) {
        api.get(`/sessions/${sid}/todos`).then(res => {
          if (res.data.found && res.data.todos?.length > 0) {
            setTodoPlans(prev => {
              const next = new Map(prev);
              next.set(sid, res.data.todos);
              return next;
            });
          }
        }).catch(() => {});
      }
    }
  }, [selectedTask?.task_id]);

  const handleClearAllSessions = async () => {
    try {
      await api.delete('/sessions');
    } catch (err) {
      console.error("Failed to clear all sessions", err);
    }
    Object.keys(localStorage)
      .filter(k => k.startsWith('chat_'))
      .forEach(k => localStorage.removeItem(k));
    
    setMessagesToClear();
    setClearDataModal('none');
  };

  const handleClearAllStorage = async () => {
    try {
      await api.delete('/storage');
    } catch (err) {
      console.error("Failed to clear storage", err);
    }
    // Clear localStorage for uploads and link replacements
    Object.keys(localStorage)
      .filter(k => k.startsWith('assignment_upload_') || k.startsWith('link_topic_'))
      .forEach(k => localStorage.removeItem(k));

    // Also remove any in-memory upload mappings
    setAssignmentUploadsMap(new Map());
    setReplacedLinksMap(new Map());
    setClearDataModal('none');
    // Force a reset key change to refresh UI
    setResetKey(k => k + 1);
  };

  const setMessagesToClear = () => {
    setSelectedTask(null);
    setCheckedTopicsMap(new Map());
    setTodoPlans(new Map());
    setInitialTodoSessions(new Set());
    setTasksOpen(true);
    setResetKey(k => k + 1);
  };

  const handleClearTodos = useCallback((sessionId: string) => {
    setTodoPlans(prev => {
      const next = new Map(prev);
      next.delete(sessionId);
      return next;
    });
    setInitialTodoSessions(prev => {
      const next = new Set(prev);
      next.delete(sessionId);
      return next;
    });
  }, []);

  const handleAddAllToCalendar = async () => {
    if (!session) return;
    setAddingAllLoading(true);
    try {
      const workRes = await api.get('/dashboard/work');
      const workData = workRes.data;
      
      const token = await session.getToken();
      let addedCount = 0;

      for (const course of workData) {
        const tasks = [...course.assignments, ...course.quizzes];
        for (const task of tasks) {
          let start = new Date();
          let end = new Date(start.getTime() + 2 * 60 * 60 * 1000);
          
          if (task.due_date) {
            end = new Date(task.due_date);
            start = new Date(end.getTime() - 2 * 60 * 60 * 1000);
            if (start.getTime() < Date.now()) {
                start = new Date();
                end = new Date(start.getTime() + 2 * 60 * 60 * 1000);
            }
          }

          try {
            await api.post('/add-event', {
              summary: `${course.course_name}: ${task.name}`,
              description: `Automatically added from TruStudy.\nTask Type: ${task.type}`,
              start_time: start.toISOString(),
              end_time: end.toISOString()
            }, { headers: { 'X-Clerk-Auth': `Bearer ${token}` } });
            addedCount++;
          } catch (e) {
            console.error("Failed to add task", task.id, e);
          }
        }
      }
      alert(`Added ${addedCount} tasks to your Google Calendar!`);
      setIsAddAllModalOpen(false);
    } catch (e) {
      console.error(e);
      alert("Failed to fetch tasks or communicate with calendar API.");
    } finally {
      setAddingAllLoading(false);
    }
  };

  const [initialTodoSessions, setInitialTodoSessions] = useState<Set<string>>(new Set());

  const handleAutoOpenTodo = useCallback((sessionId: string) => {
    if (!initialTodoSessions.has(sessionId)) {
      setTasksOpen(true);
      setInitialTodoSessions(prev => new Set(prev).add(sessionId));
      // The TasksSidebar will handle auto-expanding the to-do list via its expandedTodos state
    }
  }, [initialTodoSessions]);

  return (
    <div className="flex h-screen bg-[#f4f3ec] text-[#08060d] dark:bg-[#16171d] dark:text-[#f3f4f6] overflow-hidden text-left font-sans max-w-none w-full border-none">

      {/* Left Sidebar: Course Navigation */}
      <aside className="w-80 shrink-0 border-r border-[#e5e4e7] dark:border-[#2e303a] bg-white dark:bg-[#1f2028] flex flex-col h-full shadow-[rgba(0,0,0,0.05)_2px_0_8px_-2px] z-20">
        <div className="p-4 border-b border-[#e5e4e7] dark:border-[#2e303a] flex items-center justify-between shrink-0">
          <h1 className="text-xl font-bold tracking-tight text-[#aa3bff] dark:text-[#c084fc] m-0">TruStudy</h1>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setClearDataModal('chats')}
              className="p-1.5 hover:bg-rose-100 dark:hover:bg-rose-900/30 text-[#6b6375] hover:text-rose-500 dark:text-[#9ca3af] dark:hover:text-rose-400 rounded-lg transition-colors cursor-pointer"
              title="Clear all chat sessions"
            >
              <Trash2 size={16} strokeWidth={2.5} />
            </button>
            <button
              onClick={() => setClearDataModal('storage')}
              className="p-1.5 hover:bg-amber-100 dark:hover:bg-amber-900/30 text-[#6b6375] hover:text-amber-600 dark:text-[#9ca3af] dark:hover:text-amber-400 rounded-lg transition-colors cursor-pointer"
              title="Wipe heavy storage (uploads, embeddings)"
            >
              <Database size={16} strokeWidth={2.5} />
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
            replacedLinksMap={replacedLinksMap}
            onLinkTopicReplaced={handleLinkTopicReplaced}
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
          onClearTask={() => {
            setCheckedTopicsMap(new Map());
            setSelectedTask(null);
          }}
          selectedTopics={selectedTopicsPayload}
          resetKey={resetKey}
          onLinkTopicReplaced={handleLinkTopicReplaced}
          onTaskPlanReceived={handleTaskPlanReceived}
          assignmentUploadsMap={assignmentUploadsMap}
          onAssignmentFileUploaded={handleAssignmentFileUploaded}
          onAutoOpenTodo={handleAutoOpenTodo}
          onClearTodos={handleClearTodos}
        />
      </main>

      {/* Right Sidebar: Tasks & Workload */}
      <aside className={`shrink-0 border-l border-[#e5e4e7] dark:border-[#2e303a] bg-white dark:bg-[#1f2028] flex flex-col h-full shadow-[rgba(0,0,0,0.05)_-2px_0_8px_-2px] transition-all duration-300 ease-in-out z-20 ${tasksOpen ? 'w-96' : 'w-0 overflow-hidden border-none'}`}>
        <div className="p-4 border-b border-[#e5e4e7] dark:border-[#2e303a] shrink-0 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold tracking-tight m-0 text-left whitespace-nowrap">Pending Tasks</h2>
            <SignedOut>
              <SignInButton mode="modal">
                <button className="text-[11px] font-bold uppercase tracking-widest px-2.5 py-1 bg-[#f4f3ec] hover:bg-[#e5e4e7] dark:bg-[#3f414d] dark:hover:bg-[#4b4e5b] text-[#aa3bff] dark:text-[#c084fc] rounded-md transition-colors cursor-pointer shadow-sm">
                  Sign In
                </button>
              </SignInButton>
            </SignedOut>
            <SignedIn>
              <button
                onClick={() => setIsAddAllModalOpen(true)}
                className="p-1 min-w-[24px] min-h-[24px] flex items-center justify-center rounded-md bg-[#f4f3ec] hover:bg-[#e5e4e7] dark:bg-[#3f414d] dark:hover:bg-[#4b4e5b] text-[#aa3bff] dark:text-[#c084fc] transition-colors shadow-sm cursor-pointer border border-transparent dark:border-[#2e303a]"
                title="Add all to Google Calendar"
              >
                <CalendarPlus size={14} />
              </button>
              <UserButton appearance={{ elements: { userButtonAvatarBox: "w-6 h-6" } }} />
            </SignedIn>
          </div>
          <button onClick={() => setTasksOpen(false)} className="p-1.5 hover:bg-[#f4f3ec] dark:hover:bg-[#2e303a] rounded-lg transition-colors cursor-pointer">
            <PanelRightClose size={20} className="text-[#6b6375] dark:text-[#9ca3af]" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 bg-[#f4f3ec]/40 dark:bg-[#16171d]/40 custom-scrollbar whitespace-nowrap">
          <TasksSidebar 
            selectedTask={selectedTask} 
            onTaskSelect={handleTaskSelect} 
            todoPlans={todoPlans} 
            onTodosChange={handleTodosChange} 
            autoOpenSessionId={Array.from(initialTodoSessions).pop()}
          />
        </div>
      </aside>

      {/* Confirmation Modals */}
      {clearDataModal !== 'none' && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-white dark:bg-[#1f2028] border border-[#e5e4e7] dark:border-[#2e303a] rounded-3xl p-8 max-w-md w-full shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="flex items-center gap-4 mb-6">
              <div className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 ${
                clearDataModal === 'chats' ? 'bg-rose-100 dark:bg-rose-900/30' : 'bg-amber-100 dark:bg-amber-900/30'
              }`}>
                <AlertTriangle size={24} className={clearDataModal === 'chats' ? 'text-rose-500 dark:text-rose-400' : 'text-amber-600 dark:text-amber-400'} strokeWidth={2.5} />
              </div>
              <h3 className="text-xl font-bold text-[#08060d] dark:text-[#f3f4f6]">
                {clearDataModal === 'chats' ? 'Clear All History?' : 'Wipe Heavy Storage?'}
              </h3>
            </div>
            
            <p className="text-[#6b6375] dark:text-[#9ca3af] mb-8 leading-relaxed">
              {clearDataModal === 'chats' ? (
                <>
                  This will permanently delete <strong className="text-rose-500">all chat sessions</strong> and session memory. 
                  Your uploaded files and processed course materials will be kept under your account.
                </>
              ) : (
                <>
                  This will wipe all <strong className="text-amber-600">heavy storage items</strong> including:
                  <ul className="list-disc pl-5 mt-2 space-y-1">
                    <li>Uploaded assignment PDFs and documents</li>
                    <li>Processed course materials (manifests)</li>
                    <li>Vector search embeddings (ChromaDB)</li>
                  </ul>
                  <br/>
                  Your chat history will be preserved, but AI context may need to be re-processed on next use.
                </>
              )}
              <br/><br/>
              Are you sure you want to proceed?
            </p>

            <div className="flex items-center gap-3 w-full">
              <button
                onClick={() => setClearDataModal('none')}
                className="flex-1 py-3 px-4 bg-[#f4f3ec] hover:bg-[#e5e4e7] dark:bg-[#2e303a] dark:hover:bg-[#3f414d] text-[#08060d] dark:text-[#f3f4f6] rounded-xl font-semibold transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={clearDataModal === 'chats' ? handleClearAllSessions : handleClearAllStorage}
                className={`flex-1 py-3 px-4 text-white rounded-xl font-semibold transition-colors shadow-lg cursor-pointer ${
                  clearDataModal === 'chats' 
                    ? 'bg-rose-500 hover:bg-rose-600 shadow-rose-500/25' 
                    : 'bg-amber-600 hover:bg-amber-700 shadow-amber-600/25'
                }`}
              >
                Yes, Clear
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add All To Calendar Modal */}
      {isAddAllModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-in fade-in duration-200">
          <div className="bg-white dark:bg-[#1f2028] border border-[#e5e4e7] dark:border-[#2e303a] rounded-3xl p-8 max-w-md w-full shadow-2xl animate-in zoom-in-95 duration-200">
            <div className="flex items-center gap-4 mb-6">
              <div className="w-12 h-12 rounded-2xl bg-[#f4f3ec] dark:bg-[#3f414d] flex items-center justify-center shrink-0">
                <CalendarPlus size={24} className="text-[#aa3bff] dark:text-[#c084fc]" strokeWidth={2.5} />
              </div>
              <h3 className="text-xl font-bold text-[#08060d] dark:text-[#f3f4f6]">
                Sync All Pending Tasks?
              </h3>
            </div>
            
            <p className="text-[#6b6375] dark:text-[#9ca3af] mb-8 leading-relaxed">
              This will fetch all your pending assignments and quizzes and automatically create 2-hour study blocks for them in your personal Google Calendar.
              <br/><br/>
              Are you sure you want to proceed?
            </p>

            <div className="flex items-center gap-3 w-full">
              <button
                onClick={() => setIsAddAllModalOpen(false)}
                disabled={addingAllLoading}
                className="flex-1 py-3 px-4 bg-[#f4f3ec] hover:bg-[#e5e4e7] dark:bg-[#2e303a] dark:hover:bg-[#3f414d] text-[#08060d] dark:text-[#f3f4f6] rounded-xl font-semibold transition-colors cursor-pointer disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleAddAllToCalendar}
                disabled={addingAllLoading}
                className="flex-1 py-3 px-4 flex justify-center items-center gap-2 bg-[#aa3bff] hover:bg-[#902ee6] text-white rounded-xl font-semibold transition-colors shadow-lg cursor-pointer disabled:opacity-50"
              >
                {addingAllLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Yes, Add All'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
