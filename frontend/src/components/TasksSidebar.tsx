import { useState, useEffect } from 'react';
import { Calendar, Clock, ChevronDown, Plus, X, ArrowUp, ArrowDown, Pencil, Check } from 'lucide-react';
import api from '../lib/api';

interface Task {
  id: number | string;
  name: string;
  due_date: string | null;
  type: string;
}

interface CourseWork {
  course_id: number | string;
  course_name: string;
  assignments: Task[];
  quizzes: Task[];
}

interface TodoItem {
  id: string;
  text: string;
  completed: boolean;
  order: number;
}

export default function TasksSidebar({ selectedTask, onTaskSelect, todoPlans, onTodosChange, autoOpenSessionId }: {
  selectedTask?: any,
  onTaskSelect: (courseId: any, taskId: any, type: string, courseName?: string) => void,
  todoPlans?: Map<string, TodoItem[]>,
  onTodosChange?: (sessionId: string, todos: TodoItem[]) => void,
  autoOpenSessionId?: string,
}) {
  const [work, setWork] = useState<CourseWork[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [expandedTodos, setExpandedTodos] = useState<Set<string>>(new Set());
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editText, setEditText] = useState('');
  const [newItemTexts, setNewItemTexts] = useState<Map<string, string>>(new Map());

  useEffect(() => {
    async function loadWork() {
      try {
        const res = await api.get('/dashboard/work');
        setWork(res.data);
      } catch (err) {
        console.error("Failed to load work dashboard", err);
      } finally {
        setLoading(false);
      }
    }
    loadWork();
  }, []);

  useEffect(() => {
    if (autoOpenSessionId) {
      setExpandedTodos(prev => {
        if (prev.has(autoOpenSessionId)) return prev;
        const next = new Set(prev);
        next.add(autoOpenSessionId);
        return next;
      });
    }
  }, [autoOpenSessionId]);

  // Helper: get session_id for a task within a course
  const getSessionId = (courseId: number | string, taskId: number | string) => `${courseId}_${taskId}`;

  // Helper: get todos for a session
  const getTodos = (sessionId: string): TodoItem[] => {
    return todoPlans?.get(sessionId) || [];
  };

  // Toggle expand/collapse of a to-do section
  const toggleExpanded = (sessionId: string) => {
    setExpandedTodos(prev => {
      const next = new Set(prev);
      if (next.has(sessionId)) next.delete(sessionId);
      else next.add(sessionId);
      return next;
    });
  };

  // Toggle a todo item's completion
  const toggleTodo = (sessionId: string, itemId: string) => {
    const todos = getTodos(sessionId);
    const updated = todos.map(t => t.id === itemId ? { ...t, completed: !t.completed } : t);
    onTodosChange?.(sessionId, updated);
  };

  // Delete a todo item
  const deleteTodo = (sessionId: string, itemId: string) => {
    const todos = getTodos(sessionId).filter(t => t.id !== itemId);
    const reordered = todos.map((t, i) => ({ ...t, order: i }));
    onTodosChange?.(sessionId, reordered);
  };

  // Start inline edit
  const startEdit = (itemId: string, text: string) => {
    setEditingId(itemId);
    setEditText(text);
  };

  // Save inline edit
  const saveEdit = (sessionId: string) => {
    if (!editingId || !editText.trim()) {
      setEditingId(null);
      return;
    }
    const todos = getTodos(sessionId);
    const updated = todos.map(t => t.id === editingId ? { ...t, text: editText.trim() } : t);
    onTodosChange?.(sessionId, updated);
    setEditingId(null);
    setEditText('');
  };

  // Add a new todo item
  const addTodo = (sessionId: string) => {
    const text = (newItemTexts.get(sessionId) || '').trim();
    if (!text) return;
    const todos = getTodos(sessionId);
    const newItem: TodoItem = {
      id: Math.random().toString(36).slice(2, 10),
      text,
      completed: false,
      order: todos.length,
    };
    onTodosChange?.(sessionId, [...todos, newItem]);
    setNewItemTexts(prev => {
      const next = new Map(prev);
      next.set(sessionId, '');
      return next;
    });
  };

  // Move a todo item up or down
  const moveTodo = (sessionId: string, itemId: string, direction: 'up' | 'down') => {
    const todos = [...getTodos(sessionId)].sort((a, b) => a.order - b.order);
    const idx = todos.findIndex(t => t.id === itemId);
    if (idx < 0) return;
    const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= todos.length) return;
    [todos[idx], todos[swapIdx]] = [todos[swapIdx], todos[idx]];
    const reordered = todos.map((t, i) => ({ ...t, order: i }));
    onTodosChange?.(sessionId, reordered);
  };

  if (loading) {
    return (
      <div className="animate-pulse space-y-8 pt-2">
        {[1, 2].map(i => (
          <div key={i} className="space-y-4">
            <div className="h-5 w-40 bg-white dark:bg-[#2e303a] rounded border border-transparent dark:border-[#2e303a]"></div>
            <div className="h-28 w-full bg-white dark:bg-[#2e303a] rounded-2xl border border-transparent dark:border-[#2e303a]"></div>
            <div className="h-28 w-full bg-white dark:bg-[#2e303a] rounded-2xl border border-transparent dark:border-[#2e303a]"></div>
          </div>
        ))}
      </div>
    );
  }

  if (work.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center h-64 border-2 border-dashed border-[#e5e4e7] dark:border-[#2e303a] rounded-3xl mt-4">
        <div className="w-14 h-14 bg-white dark:bg-[#2e303a] shadow-sm rounded-full flex items-center justify-center mb-5 text-[#aa3bff] dark:text-[#c084fc]">
          <Calendar size={28} />
        </div>
        <p className="text-[#08060d] dark:text-[#f3f4f6] font-semibold text-lg tracking-tight">All caught up!</p>
        <p className="text-sm text-[#6b6375] dark:text-[#9ca3af] mt-1">No pending assignments or quizzes.</p>
      </div>
    );
  }

  const isOverdue = (dateStr: string | null): boolean => {
    if (!dateStr) return false;
    return new Date(dateStr).getTime() < new Date().getTime();
  };

  const isDueSoon = (dateStr: string | null): boolean => {
    if (!dateStr) return false;
    const diff = new Date(dateStr).getTime() - new Date().getTime();
    return diff > 0 && diff < 1000 * 60 * 60 * 24 * 3;
  };

  return (
    <div className="space-y-10 pb-8 mt-2">
      {work.map(course => {
        const tasks = [...course.assignments, ...course.quizzes];
        tasks.sort((a, b) => new Date(a.due_date || '9999').getTime() - new Date(b.due_date || '9999').getTime());

        return (
          <div key={course.course_id} className="space-y-4">
            <h3 className="text-[15px] font-bold text-[#08060d] dark:text-[#f3f4f6] truncate px-1">
              {course.course_name}
            </h3>
            <div className="space-y-3">
              {tasks.map((task, i) => {
                const overdue = isOverdue(task.due_date);
                const soon = isDueSoon(task.due_date);
                const dateObj = task.due_date ? new Date(task.due_date) : null;
                const timeOpts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' };
                const dateStr = dateObj ? dateObj.toLocaleDateString('en-US', timeOpts) : 'No Due Date';

                const isSelected = selectedTask?.task_id === task.id;
                const sessionId = getSessionId(course.course_id, task.id);
                const todos = getTodos(sessionId).sort((a, b) => a.order - b.order);
                const completedCount = todos.filter(t => t.completed).length;
                const isExpanded = expandedTodos.has(sessionId);
                const pct = todos.length > 0 ? Math.round((completedCount / todos.length) * 100) : 0;

                return (
                  <div
                    key={`${task.type}-${task.id}-${i}`}
                    className={`rounded-2xl shadow-[0_4px_12px_rgba(0,0,0,0.03)] border transition-all ${
                      isSelected
                        ? 'bg-[#f4f3ec] dark:bg-[#2e303a] border-[#aa3bff] dark:border-[#c084fc] ring-1 ring-[#aa3bff] dark:ring-[#c084fc]'
                        : 'bg-white dark:bg-[#1f2028] border-[#e5e4e7] dark:border-[#2e303a] hover:border-[#aa3bff] dark:hover:border-[#c084fc]'
                    }`}
                  >
                    {/* Task card (clickable) */}
                    <div
                      onClick={() => {
                        if (isSelected) {
                          onTaskSelect(null, null, '', undefined);
                        } else {
                          onTaskSelect(course.course_id, task.id, task.type, course.course_name);
                        }
                      }}
                      className={`p-5 cursor-pointer group ${!isSelected ? 'hover:-translate-y-0.5' : ''} transition-all`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1 min-w-0">
                          <span className="text-[11px] font-bold uppercase tracking-widest text-[#aa3bff] dark:text-[#c084fc] mb-2 block opacity-90">
                            {task.type}
                          </span>
                          <h4 className="text-[15px] font-bold text-[#08060d] dark:text-[#f3f4f6] leading-snug group-hover:text-[#aa3bff] dark:group-hover:text-[#c084fc] transition-colors whitespace-normal">
                            {task.name}
                          </h4>
                        </div>
                      </div>

                      <div className={`mt-4 pt-4 border-t border-[#f4f3ec] dark:border-[#2e303a] flex items-center text-xs font-bold uppercase tracking-wide ${
                        overdue ? 'text-red-500 dark:text-red-400' :
                        soon ? 'text-amber-500 dark:text-amber-400' :
                        'text-[#6b6375] dark:text-[#9ca3af]'
                      }`}>
                        <Clock size={14} className="mr-2 shrink-0" strokeWidth={2.5} />
                        <span className="truncate">{overdue ? 'OVERDUE — ' : ''}{dateStr}</span>
                      </div>
                    </div>

                    {/* To-Do List (only for assignments with a plan) */}
                    {task.type === 'assignment' && todos.length > 0 && (
                      <div className="px-5 pb-5">
                        <div className="pt-3 border-t border-[#e5e4e7] dark:border-[#2e303a]">
                          <button
                            onClick={(e) => { e.stopPropagation(); toggleExpanded(sessionId); }}
                            className="w-full flex items-center gap-2 text-xs font-bold text-[#6b6375] dark:text-[#9ca3af] hover:text-[#aa3bff] dark:hover:text-[#c084fc] transition-colors cursor-pointer select-none"
                          >
                            <ChevronDown size={14} className={`transition-transform duration-200 shrink-0 ${isExpanded ? 'rotate-0' : '-rotate-90'}`} />
                            <span className="uppercase tracking-widest">To-Do</span>
                            <span className="text-[#aa3bff] dark:text-[#c084fc] ml-0.5">{completedCount}/{todos.length}</span>
                            <div className="flex-1 h-1 bg-[#e5e4e7] dark:bg-[#3f414d] rounded-full ml-2 overflow-hidden">
                              <div
                                className="h-full bg-[#aa3bff] dark:bg-[#c084fc] rounded-full transition-all duration-300"
                                style={{ width: `${pct}%` }}
                              />
                            </div>
                          </button>

                          {isExpanded && (
                            <div className="mt-3 space-y-1.5">
                              {todos.map((item, idx) => (
                                <div key={item.id} className="flex items-start gap-2 group/item">
                                  <input
                                    type="checkbox"
                                    checked={item.completed}
                                    onChange={() => toggleTodo(sessionId, item.id)}
                                    className="w-3.5 h-3.5 rounded text-[#aa3bff] focus:ring-[#aa3bff] border-[#e5e4e7] dark:border-[#3f414d] dark:bg-[#1f2028] mt-0.5 shrink-0 cursor-pointer"
                                  />
                                  {editingId === item.id ? (
                                    <div className="flex-1 flex items-center gap-1">
                                      <input
                                        value={editText}
                                        onChange={(e) => setEditText(e.target.value)}
                                        onBlur={() => saveEdit(sessionId)}
                                        onKeyDown={(e) => {
                                          if (e.key === 'Enter') saveEdit(sessionId);
                                          if (e.key === 'Escape') setEditingId(null);
                                        }}
                                        autoFocus
                                        className="flex-1 text-xs bg-transparent border-b border-[#aa3bff] dark:border-[#c084fc] outline-none text-[#08060d] dark:text-[#f3f4f6] py-0.5"
                                      />
                                      <button
                                        onClick={() => saveEdit(sessionId)}
                                        className="text-[#aa3bff] dark:text-[#c084fc] p-0.5 cursor-pointer"
                                      >
                                        <Check size={12} strokeWidth={2.5} />
                                      </button>
                                    </div>
                                  ) : (
                                    <span
                                      className={`flex-1 text-xs leading-relaxed whitespace-normal ${item.completed ? 'line-through opacity-40' : 'text-[#08060d] dark:text-[#f3f4f6]'}`}
                                    >
                                      {item.text}
                                    </span>
                                  )}
                                  {/* Action buttons on hover */}
                                  {editingId !== item.id && (
                                    <div className="opacity-0 group-hover/item:opacity-100 flex items-center gap-0.5 transition-opacity shrink-0">
                                      <button onClick={() => startEdit(item.id, item.text)} className="text-[#6b6375] hover:text-[#aa3bff] dark:text-[#9ca3af] dark:hover:text-[#c084fc] p-0.5 cursor-pointer" title="Edit">
                                        <Pencil size={11} />
                                      </button>
                                      {idx > 0 && (
                                        <button onClick={() => moveTodo(sessionId, item.id, 'up')} className="text-[#6b6375] hover:text-[#aa3bff] dark:text-[#9ca3af] dark:hover:text-[#c084fc] p-0.5 cursor-pointer" title="Move up">
                                          <ArrowUp size={11} />
                                        </button>
                                      )}
                                      {idx < todos.length - 1 && (
                                        <button onClick={() => moveTodo(sessionId, item.id, 'down')} className="text-[#6b6375] hover:text-[#aa3bff] dark:text-[#9ca3af] dark:hover:text-[#c084fc] p-0.5 cursor-pointer" title="Move down">
                                          <ArrowDown size={11} />
                                        </button>
                                      )}
                                      <button onClick={() => deleteTodo(sessionId, item.id)} className="text-[#6b6375] hover:text-rose-500 dark:text-[#9ca3af] dark:hover:text-rose-400 p-0.5 cursor-pointer" title="Delete">
                                        <X size={11} />
                                      </button>
                                    </div>
                                  )}
                                </div>
                              ))}
                              {/* Add new item */}
                              <div className="flex items-center gap-2 mt-2 pt-2 border-t border-[#f4f3ec] dark:border-[#2e303a]">
                                <Plus size={12} className="text-[#aa3bff] dark:text-[#c084fc] shrink-0" />
                                <input
                                  placeholder="Add a step..."
                                  value={newItemTexts.get(sessionId) || ''}
                                  onChange={(e) => setNewItemTexts(prev => {
                                    const next = new Map(prev);
                                    next.set(sessionId, e.target.value);
                                    return next;
                                  })}
                                  onKeyDown={(e) => { if (e.key === 'Enter') addTodo(sessionId); }}
                                  className="flex-1 text-xs bg-transparent outline-none placeholder:text-[#6b6375]/50 dark:placeholder:text-[#9ca3af]/50 text-[#08060d] dark:text-[#f3f4f6]"
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
