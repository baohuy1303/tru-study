import { useState, useEffect } from 'react';
import api from '../lib/api';
import { FileText, Link as LinkIcon, Download, Clock, X } from 'lucide-react';

export default function ChatArea({ selectedTask, onClearTask }: { selectedTask: any, onClearTask: () => void }) {
  const [taskDetails, setTaskDetails] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // We only fetch for assignments for now
    if (!selectedTask || selectedTask.type !== 'assignment') return;
    
    async function fetchDetails() {
      setLoading(true);
      try {
        const res = await api.get(`/assignments/${selectedTask.org_unit_id}/${selectedTask.task_id}`);
        setTaskDetails(res.data);
      } catch (err) {
        console.error("Failed to fetch assignment details", err);
      } finally {
        setLoading(false);
      }
    }
    
    fetchDetails();
  }, [selectedTask]);

  return (
    <div className="flex-1 flex flex-col w-full h-full overflow-hidden">
      
      {/* Top Section: Task Details */}
      <div className="flex-1 overflow-y-auto w-full custom-scrollbar flex flex-col">
        {!selectedTask && (
          <div className="flex-1 flex flex-col justify-center items-center text-center opacity-80 mt-20 p-8 w-full max-w-4xl mx-auto shrink-0">
            <h2 className="text-4xl font-semibold text-[#08060d] dark:text-[#f3f4f6] tracking-tight m-0 mb-3">
              What do you want to learn today?
            </h2>
            <p className="text-lg text-[#6b6375] dark:text-[#9ca3af] m-0">
              Select course materials on the left or an assignment on the right to get started.
            </p>
          </div>
        )}

        {loading && selectedTask && (
          <div className="animate-pulse space-y-6 p-8 w-full max-w-4xl mx-auto mt-6">
            <div className="h-8 w-64 bg-white dark:bg-[#2e303a] rounded-lg"></div>
            <div className="h-32 w-full bg-white dark:bg-[#2e303a] rounded-2xl border border-transparent dark:border-[#2e303a]"></div>
          </div>
        )}

        {!loading && taskDetails && selectedTask && selectedTask.type === 'assignment' && (
          <div className="p-8 w-full max-w-5xl mx-auto">
            <div className="bg-white dark:bg-[#1f2028] p-8 md:p-10 rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.06)] border border-[#e5e4e7] dark:border-[#2e303a] mb-6 transition-all duration-300">
              <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 mb-8">
                <div className="flex items-start gap-5 flex-1 min-w-0">
                  <button 
                     onClick={onClearTask}
                     className="mt-1 p-2.5 bg-[#f4f3ec] hover:bg-[#e5e4e7] dark:bg-[#2e303a] dark:hover:bg-[#3f414d] text-[#6b6375] dark:text-[#9ca3af] rounded-xl transition-colors flex items-center justify-center cursor-pointer shrink-0"
                     title="Close Assignment View"
                  >
                    <X size={20} strokeWidth={2.5} />
                  </button>
                  <div className="flex-1 min-w-0">
                    <span className="text-xs font-extrabold uppercase tracking-widest text-[#aa3bff] dark:text-[#c084fc] mb-3 block opacity-90">
                      ASSIGNMENT
                    </span>
                    <h2 className="text-3xl font-extrabold text-[#08060d] dark:text-[#f3f4f6] tracking-tight leading-tight">
                      {taskDetails.name}
                    </h2>
                  </div>
                </div>
                
                <div className="text-left md:text-right shrink-0 flex flex-col items-start md:items-end">
                   {taskDetails.score_denominator && (
                     <div className="inline-block px-4 py-1.5 bg-[#f4f3ec] dark:bg-[#2e303a] rounded-xl text-sm font-bold text-[#08060d] dark:text-[#f3f4f6] mb-3 shadow-sm border border-[#e5e4e7] dark:border-[#3f414d] mt-4 md:mt-0">
                       Out of {taskDetails.score_denominator} Points
                     </div>
                   )}
                   {taskDetails.due_date && (
                     <div className="flex items-center text-sm font-bold text-rose-500 dark:text-rose-400 justify-start md:justify-end">
                       <Clock size={16} className="mr-2" strokeWidth={2.5} />
                       Due: {new Date(taskDetails.due_date).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
                     </div>
                   )}
                </div>
              </div>

              {taskDetails.instructions_html && (
                <div 
                  className="prose dark:prose-invert max-w-none text-[#08060d] dark:text-[#f3f4f6] opacity-90 text-[16px] leading-relaxed border-t border-[#e5e4e7] dark:border-[#2e303a] pt-8"
                  dangerouslySetInnerHTML={{ __html: taskDetails.instructions_html }} 
                />
              )}

              {/* Attachments */}
              {(taskDetails.attachments?.length > 0 || taskDetails.link_attachments?.length > 0) && (
                <div className="mt-8 pt-8 border-t border-[#e5e4e7] dark:border-[#2e303a]">
                  <h3 className="text-xs font-bold uppercase tracking-widest text-[#6b6375] dark:text-[#9ca3af] mb-4">Attachments & Links</h3>
                  <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                    {taskDetails.attachments?.map((a: any) => (
                      <div key={a.file_id} className="flex items-center p-4 bg-[#f4f3ec] dark:bg-[#2e303a]/50 rounded-2xl border border-[#e5e4e7] dark:border-[#2e303a] group transition-colors hover:border-[#aa3bff] dark:hover:border-[#c084fc]">
                        <FileText size={20} className="text-[#aa3bff] dark:text-[#c084fc] mr-4 shrink-0" />
                        <div className="flex-1 min-w-0 pr-2">
                          <p className="text-[15px] font-semibold text-[#08060d] dark:text-[#f3f4f6] truncate group-hover:text-[#aa3bff] dark:group-hover:text-[#c084fc] transition-colors">{a.file_name}</p>
                          <p className="text-xs font-medium tracking-wide text-[#6b6375] dark:text-[#9ca3af] mt-1">{(a.size / 1024).toFixed(1)} KB</p>
                        </div>
                        <button className="p-2.5 bg-white dark:bg-[#1f2028] border border-[#e5e4e7] dark:border-[#3f414d] hover:bg-[#aa3bff] hover:text-white dark:hover:bg-[#c084fc] dark:hover:text-[#08060d] rounded-xl transition-all shadow-sm text-[#08060d] dark:text-[#f3f4f6] shrink-0 cursor-pointer">
                           <Download size={16} strokeWidth={2.5} />
                        </button>
                      </div>
                    ))}
                    {taskDetails.link_attachments?.map((l: any) => (
                      <a key={l.link_id} href={l.href} target="_blank" rel="noreferrer" className="flex items-center p-4 bg-[#f4f3ec] dark:bg-[#2e303a]/50 rounded-2xl border border-[#e5e4e7] dark:border-[#2e303a] hover:border-[#aa3bff] dark:hover:border-[#c084fc] transition-colors group cursor-pointer">
                        <LinkIcon size={20} className="text-[#aa3bff] dark:text-[#c084fc] mr-4 shrink-0" />
                        <div className="flex-1 min-w-0 pr-2">
                          <p className="text-[15px] font-semibold text-[#08060d] dark:text-[#f3f4f6] truncate group-hover:text-[#aa3bff] dark:group-hover:text-[#c084fc] transition-colors">{l.link_name}</p>
                          <p className="text-xs font-medium tracking-wide text-[#6b6375] dark:text-[#9ca3af] mt-1 truncate max-w-full">{l.href}</p>
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Bottom Section: Chat Input */}
      <div className="p-8 pt-0 w-full max-w-4xl mx-auto shrink-0 mt-auto bg-[#f4f3ec] dark:bg-[#16171d]">
        <div className="w-full relative shadow-[0_8px_30px_rgb(0,0,0,0.12)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.4)] rounded-2xl border border-transparent dark:border-[#2e303a]">
          <input 
            type="text" 
            placeholder={selectedTask ? "Ask a question about this assignment..." : "Ask anything about your courses..."}
            className="w-full px-6 py-5 rounded-2xl bg-white dark:bg-[#1f2028] text-[#08060d] dark:text-[#f3f4f6] focus:outline-none focus:ring-2 focus:ring-[#aa3bff] dark:focus:ring-[#c084fc] transition-all text-lg mb-0 font-sans shadow-inner"
          />
          <button className="absolute right-4 top-1/2 transform -translate-y-1/2 p-2.5 bg-[#aa3bff] hover:bg-[#9922ff] dark:bg-[#c084fc] dark:hover:bg-[#a855f7] text-white dark:text-[#08060d] rounded-xl shadow-md transition-colors cursor-pointer border-none flex items-center justify-center">
            <svg className="w-6 h-6 ml-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
               <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
