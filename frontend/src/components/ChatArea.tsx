import { useState, useEffect, useRef } from 'react';
import api from '../lib/api';
import { FileText, Link as LinkIcon, Download, Clock, X, Terminal, Loader2, Send, Trash2, Paperclip, Pin, AlertTriangle, ExternalLink, Video, GraduationCap, Zap, Brain } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  pipelineLog?: any[];
}

interface UploadedFile {
  file_id: string;
  file_name: string;
  path: string;
  is_main: boolean;
}

export default function ChatArea({
  selectedTask,
  onClearTask,
  selectedTopics = [],
  resetKey = 0,
  onLinkTopicReplaced,
  onTaskPlanReceived,
  assignmentUploadsMap,
  onAssignmentFileUploaded,
}: {
  selectedTask: any,
  onClearTask: () => void,
  selectedTopics?: any[],
  resetKey?: number,
  onLinkTopicReplaced?: (topicId: number, topicTitle: string, uploadData: any) => void,
  onTaskPlanReceived?: (sessionId: string, plan: any[]) => void,
  assignmentUploadsMap?: Map<number, any>,
  onAssignmentFileUploaded?: (taskId: number, uploadData: any) => void,
}) {
  const [taskDetails, setTaskDetails] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [mode, setMode] = useState<'learning' | 'neutral' | 'lazy'>('neutral');
  const [streamingSteps, setStreamingSteps] = useState<string[]>([]);

  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [inaccessibleTopics, setInaccessibleTopics] = useState<any[]>([]);
  const [uploadingForTopic, setUploadingForTopic] = useState<number | null>(null);
  const [tooLongVideos, setTooLongVideos] = useState<any[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [input]);

  // Auto-scroll chat to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };
  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  // Reset uploaded files, inaccessible topics, and too-long videos when task changes
  // Also restore persisted main file for link-only assignments
  useEffect(() => {
    setUploadedFiles([]);
    setInaccessibleTopics([]);
    setTooLongVideos([]);
    if (selectedTask?.task_id && assignmentUploadsMap?.has(selectedTask.task_id)) {
      const saved = assignmentUploadsMap.get(selectedTask.task_id);
      setUploadedFiles([{ ...saved, is_main: true }]);
    }
  }, [selectedTask?.task_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reset everything when resetKey changes (clear-all triggered from Dashboard)
  useEffect(() => {
    if (resetKey > 0) {
      setUploadedFiles([]);
      setMessages([]);
      setSessionId(null);
      setInaccessibleTopics([]);
      setTooLongVideos([]);
    }
  }, [resetKey]);

  const [loadedTaskId, setLoadedTaskId] = useState<any>(null);
  const currentSessionIdRef = useRef(sessionId);
  
  useEffect(() => {
    currentSessionIdRef.current = sessionId;
  }, [sessionId]);

  // Load persistence
  useEffect(() => {
    const activeSessionId = currentSessionIdRef.current;
    if (activeSessionId?.startsWith("freeform_")) {
      api.delete(`/sessions/id/${activeSessionId}`).catch(e => console.error("Freeform cleanup failed", e));
    }

    const taskId = selectedTask?.task_id || null;
    if (taskId) {
      const saved = localStorage.getItem(`chat_${taskId}`);
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          setMessages(parsed.messages || []);
          setSessionId(parsed.sessionId || null);
        } catch (e) {
          setMessages([]);
          setSessionId(null);
        }
      } else {
        setMessages([]);
        setSessionId(null);
      }
    } else {
      setMessages([]);
      setSessionId(null);
    }
    setLoadedTaskId(taskId);
  }, [selectedTask?.task_id, selectedTask?.org_unit_id, selectedTask?.type]);

  // Save persistence
  useEffect(() => {
    if (selectedTask?.task_id && loadedTaskId === selectedTask.task_id && messages.length > 0) {
      localStorage.setItem(`chat_${selectedTask.task_id}`, JSON.stringify({ messages, sessionId }));
    }
  }, [messages, sessionId, selectedTask?.task_id, loadedTaskId]);

  useEffect(() => {
    if (!selectedTask || selectedTask.type !== 'assignment') {
      setTaskDetails(null);
      return;
    }

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
  }, [selectedTask?.task_id, selectedTask?.org_unit_id, selectedTask?.type]);

  const handleClearChat = async () => {
    try {
      if (sessionId) {
        await api.delete(`/sessions/id/${sessionId}`);
      } else if (selectedTask) {
        await api.delete(`/sessions/0/${selectedTask.task_id}`); // fallback if very old session
      }
      setMessages([]);
      setSessionId(null);
      setUploadedFiles([]);
      setInaccessibleTopics([]);
      setTooLongVideos([]);
      if (selectedTask) {
        localStorage.removeItem(`chat_${selectedTask.task_id}`);
      }
    } catch (e) {
      console.error("Failed to clear backend session", e);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const token = localStorage.getItem('bs_token');
      const res = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        headers: { 'Authorization': token ? `Bearer ${token}` : '' },
        body: formData,
      });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      const data = await res.json();

      // In freeform mode, first upload auto-becomes main
      const isMain = !selectedTask && uploadedFiles.length === 0;
      setUploadedFiles(prev => [...prev, { ...data, is_main: isMain }]);
    } catch (err) {
      console.error("Upload failed", err);
    } finally {
      setIsUploading(false);
    }
  };

  const handleUploadForTopic = async (e: React.ChangeEvent<HTMLInputElement>, topic: any) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';
    setUploadingForTopic(topic.id);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const token = localStorage.getItem('bs_token');
      const res = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        headers: { 'Authorization': token ? `Bearer ${token}` : '' },
        body: formData,
      });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      const data = await res.json();
      onLinkTopicReplaced?.(topic.id, topic.title, data);
      setInaccessibleTopics(prev => prev.filter(t => t.id !== topic.id));
    } catch (err) {
      console.error("Upload failed", err);
    } finally {
      setUploadingForTopic(null);
    }
  };

  const handlePinFile = (file_id: string) => {
    // Only allow pinning in freeform mode (no selected assignment task)
    if (selectedTask) return;
    setUploadedFiles(prev => prev.map(f => ({ ...f, is_main: f.file_id === file_id })));
  };

  const handleRemoveFile = (file_id: string) => {
    setUploadedFiles(prev => {
      const remaining = prev.filter(f => f.file_id !== file_id);
      // If we removed the main file, make the first remaining file the main
      if (prev.find(f => f.file_id === file_id)?.is_main && remaining.length > 0) {
        remaining[0].is_main = true;
      }
      return remaining;
    });
  };

  const handleDownload = async (fileId: number, fileName: string) => {
    try {
      const res = await api.get(
        `/courses/${selectedTask.org_unit_id}/assignments/${selectedTask.task_id}/attachments/${fileId}/download`,
        { responseType: 'blob' }
      );

      const url = window.URL.createObjectURL(res.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = fileName;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Download failed", err);
    }
  };

  // Check if assignment has only external links and no downloadable attachments
  const hasOnlyExternalLinks = taskDetails &&
    (taskDetails.link_attachments?.length > 0) &&
    (!taskDetails.attachments || taskDetails.attachments.length === 0);

  const hasUploadedMainFile = uploadedFiles.some(f => f.is_main);

  const canChat = selectedTask
    ? (selectedTask.type !== 'assignment'
       || !hasOnlyExternalLinks
       || hasUploadedMainFile
       || selectedTopics.length > 0)
    : (uploadedFiles.length > 0 || selectedTopics.length > 0);

  // Handler for the amber-banner "upload assignment file" — persists via Dashboard
  const handleAssignmentBannerUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedTask?.task_id) return;
    e.target.value = '';
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const token = localStorage.getItem('bs_token');
      const res = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        headers: { 'Authorization': token ? `Bearer ${token}` : '' },
        body: formData,
      });
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
      const data = await res.json();
      const fileWithMain = { ...data, is_main: true };
      setUploadedFiles(prev => [fileWithMain, ...prev.filter(f => !f.is_main)]);
      onAssignmentFileUploaded?.(selectedTask.task_id, fileWithMain);
    } catch (err) {
      console.error("Upload failed", err);
    } finally {
      setIsUploading(false);
    }
  };

  const handleSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!input.trim() || !canChat || isTyping) return;

    const userMsg = input.trim();
    setInput('');

    const newMessages = [...messages, { role: 'user' as const, content: userMsg }];
    setMessages(newMessages);
    setIsTyping(true);
    setStreamingSteps([]);

    try {
      const payload = {
        prompt: userMsg,
        course_id: selectedTask?.org_unit_id || 0,
        org_unit_id: selectedTask?.org_unit_id || 0,
        course_name: selectedTask?.course_name || "",
        assignment_id: selectedTask?.task_id || null,
        assignment_text: taskDetails?.instructions_html || "",
        assignment_attachments: taskDetails?.attachments?.map((a: any) => ({
          file_id: a.file_id,
          file_name: a.file_name,
          size: a.size
        })) || [],
        selected_topic_ids: selectedTopics,
        uploaded_files: uploadedFiles,
        chat_history: messages.map(m => ({ role: m.role, content: m.content })),
        session_id: sessionId,
        mode: mode
      };

      const token = localStorage.getItem('bs_token');
      const res = await fetch('http://localhost:8000/api/chat/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : ''
        },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
      }

      const reader = res.body?.getReader();
      const decoder = new TextDecoder("utf-8");
      let done = false;
      let buffer = '';

      while (!done && reader) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          let boundary = buffer.indexOf('\n\n');
          while (boundary !== -1) {
            const chunk = buffer.slice(0, boundary).trim();
            buffer = buffer.slice(boundary + 2);
            if (chunk.startsWith('data: ')) {
              const dataStr = chunk.replace('data: ', '');
              if (dataStr) {
                try {
                  const data = JSON.parse(dataStr);
                  if (data.type === 'progress') {
                    setStreamingSteps(prev => [...prev, data.node]);
                  } else if (data.type === 'result') {
                    setSessionId(data.session_id);
                    setMessages(prev => [...prev, {
                      role: 'assistant',
                      content: data.response,
                      pipelineLog: data.pipeline_log
                    }]);
                    if (data.inaccessible_topics?.length > 0) {
                      setInaccessibleTopics(data.inaccessible_topics);
                    }
                    if (data.too_long_videos?.length > 0) {
                      setTooLongVideos(data.too_long_videos);
                    }
                    if (data.task_plan?.length > 0 && data.session_id) {
                      onTaskPlanReceived?.(data.session_id, data.task_plan);
                    }
                  }
                } catch(e) {
                  console.error("Error parsing stream chunk", e, dataStr);
                }
              }
            }
            boundary = buffer.indexOf('\n\n');
          }
        }
      }

    } catch (err) {
      console.error("Chat API failed", err);
      setMessages(prev => [...prev, { role: 'assistant', content: "Sorry, I encountered an error processing your request." }]);
    } finally {
      setIsTyping(false);
      setStreamingSteps([]);
    }
  };

  return (
    <div className="flex-1 flex flex-col w-full h-full overflow-hidden">

      {/* Top Section: Task Details & Chat History */}
      <div className="flex-1 overflow-y-auto w-full custom-scrollbar flex flex-col pb-6">
        {!selectedTask && messages.length === 0 && uploadedFiles.length === 0 && selectedTopics.length === 0 && (
          <div className="flex-1 flex flex-col justify-center items-center text-center opacity-80 mt-20 p-8 w-full max-w-4xl mx-auto shrink-0">
            <h2 className="text-4xl font-semibold text-[#08060d] dark:text-[#f3f4f6] tracking-tight m-0 mb-3">
              What do you want to learn today?
            </h2>
            <p className="text-lg text-[#6b6375] dark:text-[#9ca3af] m-0">
              Select an assignment on the right, pick course materials from the left, or upload your own files below.
            </p>
          </div>
        )}

        {loading && selectedTask && (
          <div className="animate-pulse space-y-6 p-8 w-full max-w-4xl mx-auto mt-6">
            <div className="h-8 w-64 bg-white dark:bg-[#2e303a] rounded-lg"></div>
            <div className="h-32 w-full bg-white dark:bg-[#2e303a] rounded-2xl border border-transparent dark:border-[#2e303a]"></div>
          </div>
        )}

        {/* Assignment Details Banner */}
        {!loading && taskDetails && selectedTask && selectedTask.type === 'assignment' && (
          <div className="p-8 pb-4 w-full max-w-5xl mx-auto">
            <div className="bg-white dark:bg-[#1f2028] p-8 md:p-10 rounded-[2rem] shadow-[0_8px_30px_rgb(0,0,0,0.06)] border border-[#e5e4e7] dark:border-[#2e303a] mb-2 transition-all duration-300 relative">
              <div className="flex flex-col md:flex-row md:items-start justify-between gap-6 mb-8">
                <div className="flex items-start gap-5 flex-1 min-w-0">
                  <div className="flex items-center gap-2 mt-1 shrink-0">
                    <button
                       onClick={onClearTask}
                       className="p-2.5 bg-[#f4f3ec] hover:bg-[#e5e4e7] dark:bg-[#2e303a] dark:hover:bg-[#3f414d] text-[#6b6375] dark:text-[#9ca3af] rounded-xl transition-colors flex items-center justify-center cursor-pointer"
                       title="Close Assignment View"
                    >
                      <X size={20} strokeWidth={2.5} />
                    </button>
                    {messages.length > 0 && (
                      <button
                        onClick={handleClearChat}
                        className="p-2.5 bg-[#f4f3ec] hover:bg-rose-100 dark:bg-[#2e303a] dark:hover:bg-rose-900/30 text-[#6b6375] hover:text-rose-500 dark:text-[#9ca3af] dark:hover:text-rose-400 rounded-xl transition-colors flex items-center justify-center cursor-pointer"
                        title="Clear chat history"
                      >
                        <Trash2 size={18} strokeWidth={2.5} />
                      </button>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <span className="text-xs font-extrabold uppercase tracking-widest text-[#aa3bff] dark:text-[#c084fc] mb-3 block opacity-90">
                      ASSIGNMENT {selectedTask.course_name ? `• ${selectedTask.course_name}` : ''}
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

              {/* External link warning + upload slot */}
              {hasOnlyExternalLinks && (
                <div className="mt-8 p-5 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700 rounded-2xl">
                  <div className="flex items-start gap-3 mb-3">
                    <AlertTriangle size={18} className="text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" strokeWidth={2.5} />
                    <div>
                      <p className="text-sm font-bold text-amber-800 dark:text-amber-200 mb-1">External assignment file detected</p>
                      <p className="text-sm text-amber-700 dark:text-amber-300">
                        This assignment links to an external file (e.g. Google Drive or Docs). We may not be able to download it automatically. Upload the file manually below for best results.
                      </p>
                    </div>
                  </div>
                  <label className="inline-flex items-center gap-2 px-4 py-2 bg-amber-100 dark:bg-amber-800/40 hover:bg-amber-200 dark:hover:bg-amber-700/50 text-amber-800 dark:text-amber-200 rounded-xl text-sm font-semibold cursor-pointer transition-colors border border-amber-200 dark:border-amber-700">
                    <Paperclip size={14} strokeWidth={2.5} />
                    Upload assignment file
                    <input type="file" className="hidden" accept=".pdf,.doc,.docx,.txt,.pptx,.ppt,.mp4,.mov,.webm,.mkv,.avi" onChange={handleAssignmentBannerUpload} />
                  </label>
                </div>
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
                        <button
                          onClick={() => handleDownload(a.file_id, a.file_name)}
                          className="p-2.5 bg-white dark:bg-[#1f2028] border border-[#e5e4e7] dark:border-[#3f414d] hover:bg-[#aa3bff] hover:text-white dark:hover:bg-[#c084fc] dark:hover:text-[#08060d] rounded-xl transition-all shadow-sm text-[#08060d] dark:text-[#f3f4f6] shrink-0 cursor-pointer"
                        >
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

        {/* Inaccessible course materials banner */}
        {inaccessibleTopics.length > 0 && (
          <div className="px-8 pb-4 w-full max-w-5xl mx-auto">
            <div className="p-5 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-700 rounded-2xl">
              <div className="flex items-start gap-3 mb-3">
                <ExternalLink size={18} className="text-blue-600 dark:text-blue-400 shrink-0 mt-0.5" strokeWidth={2.5} />
                <div>
                  <p className="text-sm font-bold text-blue-800 dark:text-blue-200 mb-1">Some course materials couldn't be accessed</p>
                  <p className="text-sm text-blue-700 dark:text-blue-300">
                    These resources are external links. Download them manually and upload here for the best results.
                  </p>
                </div>
              </div>
              <div className="flex flex-col gap-2 mt-3">
                {inaccessibleTopics.map((topic: any) => (
                  <div key={topic.id} className="flex items-center gap-3 p-3 bg-white dark:bg-[#1f2028] rounded-xl border border-blue-100 dark:border-blue-800">
                    <ExternalLink size={14} className="text-blue-500 shrink-0" />
                    <a href={topic.url} target="_blank" rel="noreferrer"
                       className="text-sm font-semibold text-blue-700 dark:text-blue-300 flex-1 hover:underline truncate">
                      {topic.title}
                    </a>
                    <label className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-100 dark:bg-blue-800/40 hover:bg-blue-200 dark:hover:bg-blue-700/50 text-blue-800 dark:text-blue-200 rounded-lg text-xs font-semibold cursor-pointer transition-colors shrink-0 border border-blue-200 dark:border-blue-700">
                      {uploadingForTopic === topic.id ? <Loader2 size={12} className="animate-spin" /> : <Paperclip size={12} strokeWidth={2.5} />}
                      Upload
                      <input type="file" className="hidden" accept=".pdf,.doc,.docx,.txt,.pptx,.ppt,.mp4,.mov,.webm,.mkv,.avi"
                             onChange={(e) => handleUploadForTopic(e, topic)}
                             disabled={uploadingForTopic === topic.id} />
                    </label>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Too-long videos banner */}
        {tooLongVideos.length > 0 && (
          <div className="px-8 pb-4 w-full max-w-5xl mx-auto">
            <div className="p-5 bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-700 rounded-2xl">
              <div className="flex items-start gap-3">
                <AlertTriangle size={18} className="text-orange-600 dark:text-orange-400 shrink-0 mt-0.5" strokeWidth={2.5} />
                <div>
                  <p className="text-sm font-bold text-orange-800 dark:text-orange-200 mb-1">
                    Some video materials couldn't be transcribed
                  </p>
                  <p className="text-sm text-orange-700 dark:text-orange-300 mb-3">
                    Videos over 10 minutes cannot be transcribed in the current plan. Shorter videos are transcribed automatically when selected.
                  </p>
                  <div className="flex flex-col gap-1.5">
                    {tooLongVideos.map((v: any) => (
                      <div key={v.id} className="flex items-center gap-2 text-sm text-orange-700 dark:text-orange-300">
                        <Video size={14} className="shrink-0" />
                        <span className="font-medium truncate">{v.title}</span>
                        <span className="text-xs opacity-70">
                          {v.reason === 'transcription_failed'
                            ? 'Transcription failed'
                            : `~${v.duration_estimate_min} min`}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Chat Thread */}
        <div className="w-full max-w-4xl mx-auto px-4 lg:px-8 space-y-6 shrink-0 pb-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div
                className={`max-w-[85%] md:max-w-[75%] rounded-2xl p-5 ${
                  msg.role === 'user'
                    ? 'bg-[#aa3bff] text-white rounded-br-sm'
                    : 'bg-white dark:bg-[#1f2028] text-[#08060d] dark:text-[#f3f4f6] border border-[#e5e4e7] dark:border-[#2e303a] rounded-bl-sm shadow-sm'
                }`}
              >
                {msg.role === 'user' ? (
                  <div className="whitespace-pre-wrap text-[15px] leading-[1.6] break-words">{msg.content}</div>
                ) : (
                  <div className="prose dark:prose-invert max-w-none text-[#08060d] dark:text-[#f3f4f6] break-words overflow-x-hidden text-[15px] leading-[1.6]">
                    <ReactMarkdown 
                      remarkPlugins={[remarkGfm]}
                      components={{
                        code({ node, inline, className, children, ...props }: any) {
                          const match = /language-(\w+)/.exec(className || '');
                          return !inline && match ? (
                            <div className="rounded-xl overflow-hidden my-4 border border-[#e5e4e7] dark:border-[#3f414d] shadow-sm relative group">
                              <div className="flex items-center justify-between px-4 py-1.5 bg-[#f4f3ec] dark:bg-[#2e303a] border-b border-[#e5e4e7] dark:border-[#3f414d]">
                                <span className="text-[11px] font-bold text-[#6b6375] dark:text-[#9ca3af] uppercase tracking-wider">{match[1]}</span>
                                <button
                                  onClick={() => navigator.clipboard.writeText(String(children).replace(/\n$/, ''))}
                                  className="text-[10px] font-bold text-[#6b6375] dark:text-[#9ca3af] hover:text-[#aa3bff] transition-colors bg-white dark:bg-[#1f2028] px-2 py-0.5 rounded shadow-sm border border-[#e5e4e7] dark:border-[#3f414d] cursor-pointer"
                                >
                                  COPY
                                </button>
                              </div>
                              <SyntaxHighlighter
                                style={vscDarkPlus as any}
                                language={match[1]}
                                PreTag="div"
                                customStyle={{ margin: 0, padding: '1.25rem', background: '#1e1e1e', fontSize: '14px', lineHeight: '1.5' }}
                                {...props}
                              >
                                {String(children).replace(/\n$/, '')}
                              </SyntaxHighlighter>
                            </div>
                          ) : (
                            <code className="bg-[#f4f3ec] dark:bg-[#2e303a] px-1.5 py-0.5 rounded-md text-[#aa3bff] dark:text-[#c084fc] font-mono text-[0.9em]" {...props}>
                              {children}
                            </code>
                          );
                        }
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                )}
              </div>
              {/* Pipeline Log visualization (only for assistant messages) */}
              {msg.role === 'assistant' && msg.pipelineLog && msg.pipelineLog.length > 0 && (
                <div className="mt-2 flex items-center gap-2 px-1 text-[10px] text-[#6b6375] dark:text-[#9ca3af] opacity-50 hover:opacity-100 transition-opacity select-none group">
                  <span className="font-bold uppercase tracking-widest flex items-center gap-1">
                    <Terminal size={10} className="opacity-70" />
                    Trace
                  </span>
                  <div className="flex items-center gap-1.5 overflow-x-auto whitespace-nowrap scrollbar-none">
                    {msg.pipelineLog!.map((log: any, idx: number) => (
                      <div key={idx} className="flex items-center text-[10px]">
                        {log.status === 'done' && <span className="text-emerald-500 font-bold mr-0.5 animate-in fade-in zoom-in-50 duration-500">✓</span>}
                        {log.status === 'error' && <span className="text-rose-500 font-bold mr-0.5">✗</span>}
                        <span className={`capitalize ${log.status === 'error' ? 'text-rose-500 font-semibold' : 'text-[#6b6375] dark:text-[#9ca3af]'}`}>
                          {log.node.replace(/_/g, ' ')}
                        </span>
                        {idx < msg.pipelineLog!.length - 1 && <span className="mx-1.5 opacity-20 text-[9px]">/</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}

          {isTyping && (
            <div className="flex justify-start">
              <div className="bg-white dark:bg-[#1f2028] border border-[#e5e4e7] dark:border-[#2e303a] rounded-2xl rounded-bl-sm p-5 shadow-sm min-w-[280px] flex flex-col gap-3 transition-all animate-in fade-in slide-in-from-left-4 duration-500">
                {streamingSteps.length === 0 && (
                  <div className="flex items-center gap-3">
                    <Loader2 className="animate-spin text-[#aa3bff]" size={18} />
                    <span className="text-sm font-bold text-[#6b6375] dark:text-[#9ca3af]">TruStudy is thinking...</span>
                  </div>
                )}
                {streamingSteps.map((step, idx) => (
                  <div key={idx} className="flex items-center gap-3 animate-in fade-in slide-in-from-left-2 duration-300">
                    {idx === streamingSteps.length - 1 ? (
                      <Loader2 className="animate-spin text-[#aa3bff]" size={14} />
                    ) : (
                      <div className="w-3.5 h-3.5 rounded-full bg-emerald-500/10 dark:bg-emerald-500/20 flex items-center justify-center">
                        <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                      </div>
                    )}
                    <span className={`text-[13px] font-semibold capitalize ${idx === streamingSteps.length - 1 ? 'text-[#08060d] dark:text-[#f3f4f6]' : 'text-[#6b6375] dark:text-[#9ca3af] opacity-60'}`}>
                      {step.replace(/_/g, ' ')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

      </div>

      {/* Bottom Section: Chat Input */}
      <div className="p-8 pt-0 w-full max-w-4xl mx-auto shrink-0 mt-auto bg-[#f4f3ec] dark:bg-[#16171d] relative">

        {/* Uploaded files row */}
        {uploadedFiles.length > 0 && (
          <div className="mb-3 flex flex-wrap gap-2">
            {uploadedFiles.map(f => (
              <div
                key={f.file_id}
                className={`inline-flex items-center gap-1.5 pl-3 pr-2 py-1.5 rounded-xl text-[12px] font-semibold border transition-all ${
                  f.is_main
                    ? 'bg-[#aa3bff]/10 border-[#aa3bff] text-[#aa3bff] dark:text-[#c084fc]'
                    : 'bg-white dark:bg-[#1f2028] border-[#e5e4e7] dark:border-[#2e303a] text-[#6b6375] dark:text-[#9ca3af]'
                }`}
              >
                <FileText size={12} strokeWidth={2.5} />
                <span className="max-w-[120px] truncate">{f.file_name}</span>
                {f.is_main && <span className="text-[10px] font-bold opacity-70 ml-0.5">MAIN</span>}
                {/* Pin button — only in freeform mode */}
                {!selectedTask && !f.is_main && (
                  <button
                    onClick={() => handlePinFile(f.file_id)}
                    className="ml-1 p-0.5 hover:text-[#aa3bff] dark:hover:text-[#c084fc] transition-colors cursor-pointer"
                    title="Set as main assignment file"
                  >
                    <Pin size={11} strokeWidth={2.5} />
                  </button>
                )}
                <button
                  onClick={() => handleRemoveFile(f.file_id)}
                  className="ml-0.5 p-0.5 hover:text-rose-500 transition-colors cursor-pointer"
                  title="Remove file"
                >
                  <X size={11} strokeWidth={2.5} />
                </button>
              </div>
            ))}
          </div>
        )}

        <form 
          onSubmit={handleSubmit} 
          className={`w-full relative shadow-[0_8px_30px_rgb(0,0,0,0.12)] dark:shadow-[0_8px_30px_rgb(0,0,0,0.4)] rounded-[1.5rem] border font-sans flex flex-col transition-all duration-200 group
            ${!canChat 
              ? 'bg-gray-100 dark:bg-gray-800/40 border-gray-200 dark:border-gray-700 opacity-100 cursor-not-allowed shadow-none' 
              : 'bg-white dark:bg-[#1f2028] border-transparent dark:border-[#2e303a] focus-within:ring-2 focus-within:ring-[#aa3bff] dark:focus-within:ring-[#c084fc]'
            }`}
        >

          <textarea
            ref={textareaRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            disabled={!canChat || isTyping}
            placeholder={
              !canChat
                ? (hasOnlyExternalLinks
                    ? "Upload the assignment file above to start chatting..."
                    : "Upload a file or select materials to start chatting...")
                : isTyping ? "Wait for response..."
                : selectedTask ? "Ask a question about this assignment..."
                : "Ask anything about your uploaded files or selected materials..."
            }
            className="w-full px-6 pt-5 pb-2 rounded-[1.5rem] bg-transparent text-[#08060d] dark:text-[#f3f4f6] focus:outline-none text-[16px] border-none resize-none overflow-y-auto custom-scrollbar max-h-[300px]"
          />

          <div className="flex items-center justify-between px-4 pb-4 pt-1 gap-3">
            {/* Left: file upload + selected topics + mode toggle */}
            <div className="flex items-center gap-2 flex-1 overflow-x-auto custom-scrollbar min-w-0">
              
              {/* Mode Toggle */}
              <div className="shrink-0 flex items-center bg-[#f4f3ec] dark:bg-[#2e303a] rounded-full p-1 cursor-pointer select-none shadow-inner border border-[#e5e4e7] dark:border-[#3f414d]">
                <button
                  type="button"
                  onClick={(e) => { e.preventDefault(); setMode('learning'); }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] font-bold transition-all duration-200 ${mode === 'learning' ? 'bg-white dark:bg-[#1f2028] text-[#aa3bff] dark:text-[#c084fc] shadow-sm' : 'text-[#6b6375] dark:text-[#9ca3af] hover:text-[#aa3bff] dark:hover:text-[#c084fc]'}`}
                >
                  <GraduationCap size={15} strokeWidth={2.5} />
                  Learning
                </button>
                <button
                  type="button"
                  onClick={(e) => { e.preventDefault(); setMode('neutral'); }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] font-bold transition-all duration-200 ${mode === 'neutral' ? 'bg-white dark:bg-[#1f2028] text-[#aa3bff] dark:text-[#c084fc] shadow-sm' : 'text-[#6b6375] dark:text-[#9ca3af] hover:text-[#aa3bff] dark:hover:text-[#c084fc]'}`}
                >
                  <Brain size={15} strokeWidth={2.5} />
                  Buddy
                </button>
                <button
                  type="button"
                  onClick={(e) => { e.preventDefault(); setMode('lazy'); }}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] font-bold transition-all duration-200 ${mode === 'lazy' ? 'bg-white dark:bg-[#1f2028] text-[#aa3bff] dark:text-[#c084fc] shadow-sm' : 'text-[#6b6375] dark:text-[#9ca3af] hover:text-[#aa3bff] dark:hover:text-[#c084fc]'}`}
                >
                  <Zap size={15} strokeWidth={2.5} />
                  Lazy
                </button>
              </div>

              {/* Upload button */}
              <label className={`shrink-0 p-2 rounded-lg transition-colors cursor-pointer ${isUploading ? 'opacity-50 cursor-not-allowed' : 'hover:bg-[#f4f3ec] dark:hover:bg-[#2e303a]'} text-[#6b6375] dark:text-[#9ca3af]`} title="Upload a file">
                {isUploading ? <Loader2 size={18} className="animate-spin" /> : <Paperclip size={18} strokeWidth={2.5} />}
                <input
                  ref={fileInputRef}
                  type="file"
                  className="hidden"
                  accept=".pdf,.doc,.docx,.txt,.pptx,.ppt,.mp4,.mov,.webm,.mkv,.avi"
                  onChange={handleFileUpload}
                  disabled={isUploading}
                />
              </label>

              {/* Selected course topics */}
              {selectedTopics && selectedTopics.length > 0 && selectedTopics.map((t, idx) => (
                <span key={idx} className="inline-flex items-center px-2.5 py-1.5 rounded-lg text-[11px] font-bold bg-[#f4f3ec] dark:bg-[#2e303a] text-[#aa3bff] dark:text-[#c084fc] whitespace-nowrap border border-[#e5e4e7] dark:border-[#3f414d] shadow-sm shrink-0">
                  <FileText size={12} className="mr-1.5" />
                  {t.title}
                </span>
              ))}
            </div>

            {/* Right: send button */}
            <button
              type="submit"
              disabled={!input.trim() || !canChat || isTyping}
              className={`p-2.5 rounded-xl shadow-md transition-all duration-200 border-none flex items-center justify-center shrink-0
                ${(!input.trim() || !canChat || isTyping)
                  ? 'bg-gray-200 dark:bg-gray-700 text-gray-400 dark:text-gray-500 cursor-not-allowed'
                  : 'bg-[#aa3bff] hover:bg-[#9922ff] text-white cursor-pointer hover:scale-105 active:scale-95'
                }`}
            >
              <Send size={20} strokeWidth={2.5} className="-ml-0.5 mt-0.5" />
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
