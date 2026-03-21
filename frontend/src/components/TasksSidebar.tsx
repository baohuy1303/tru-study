import { useState, useEffect } from 'react';
import { Calendar, Clock } from 'lucide-react';
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

export default function TasksSidebar({ selectedTask, onTaskSelect }: { selectedTask?: any, onTaskSelect: (courseId: any, taskId: any, type: string) => void }) {
  const [work, setWork] = useState<CourseWork[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

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

  // Calculate urgency colors based on date
  const isOverdue = (dateStr: string | null): boolean => {
    if (!dateStr) return false;
    return new Date(dateStr).getTime() < new Date().getTime();
  };

  const isDueSoon = (dateStr: string | null): boolean => {
    if (!dateStr) return false;
    const diff = new Date(dateStr).getTime() - new Date().getTime();
    return diff > 0 && diff < 1000 * 60 * 60 * 24 * 3; // within 3 days
  };

  return (
    <div className="space-y-10 pb-8 mt-2">
      {work.map(course => {
        const tasks = [...course.assignments, ...course.quizzes];
        // Sort by due date
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

                return (
                  <div 
                    key={`${task.type}-${task.id}-${i}`} 
                    onClick={() => {
                      if (isSelected) {
                        onTaskSelect(null, null, '');
                      } else {
                        onTaskSelect(course.course_id, task.id, task.type);
                      }
                    }}
                    className={`p-5 rounded-2xl shadow-[0_4px_12px_rgba(0,0,0,0.03)] border transition-all cursor-pointer group ${
                      isSelected 
                        ? 'bg-[#f4f3ec] dark:bg-[#2e303a] border-[#aa3bff] dark:border-[#c084fc] ring-1 ring-[#aa3bff] dark:ring-[#c084fc]' 
                        : 'bg-white dark:bg-[#1f2028] border-[#e5e4e7] dark:border-[#2e303a] hover:border-[#aa3bff] dark:hover:border-[#c084fc] hover:-translate-y-0.5'
                    }`}
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
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
