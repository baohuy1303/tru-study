import { useState, useEffect } from 'react';
import { ChevronRight, ChevronDown, Folder, FileText, BookOpen } from 'lucide-react';
import api from '../lib/api';

// TreeNode component for recursive rendering
function TreeNode({ 
  node, 
  orgUnitId, 
  level = 0,
  checkedTopics,
  onTopicToggle
}: { 
  node: any, 
  orgUnitId?: any, 
  level?: number,
  checkedTopics?: Set<number>,
  onTopicToggle?: (topic: any, checked: boolean) => void
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [children, setChildren] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(false);

  // Type: 0 = Module, 1 = Topic
  const isModule = level === 0 || node.type === 0;
  const isSelectableTopic = !isModule && node.topic_type === 1;
  const isChecked = checkedTopics ? checkedTopics.has(node.id) : false;

  const handleToggle = async (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (!isModule) {
      if (isSelectableTopic && onTopicToggle) {
        onTopicToggle(node, !isChecked);
      }
      return;
    }
    
    setIsOpen(!isOpen);
    
    if (!isOpen && !children && !loading) {
      setLoading(true);
      try {
        let res;
        if (level === 0) {
          // Level 0 is a Course -> fetch root modules
          res = await api.get(`/courses/${node.id}/modules`);
        } else {
          // Level > 0 is a Module -> fetch child topics
          res = await api.get(`/courses/${orgUnitId}/modules/${node.id}`);
        }
        setChildren(res.data);
      } catch (err) {
        console.error("Failed to load children", err);
      } finally {
        setLoading(false);
      }
    }
  };

  const padLeft = level * 16 + 8;

  return (
    <div className="w-full">
      <div 
        className={`flex items-start py-2.5 hover:bg-[#f4f3ec] dark:hover:bg-[#2e303a] cursor-pointer rounded-xl transition-colors group ${level === 0 ? 'mt-2 mb-1 px-3' : 'mb-0.5 pr-3'}`}
        style={{ paddingLeft: level === 0 ? '12px' : `${padLeft}px` }}
        onClick={handleToggle}
      >
        <div className="w-5 h-5 flex items-center justify-center mr-1.5 mt-0.5 text-[#6b6375] dark:text-[#9ca3af] group-hover:text-[#aa3bff] dark:group-hover:text-[#c084fc] transition-colors shrink-0">
          {isModule ? (
            isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />
          ) : isSelectableTopic ? (
            <input 
              type="checkbox"
              checked={isChecked}
              onChange={() => {}} // dummy onChange since event is handled by onClick
              className="w-3.5 h-3.5 rounded text-[#aa3bff] focus:ring-[#aa3bff] border-[#e5e4e7] dark:border-[#3f414d] dark:bg-[#1f2028]"
            />
          ) : (
            <span className="w-4 h-4" /> // spacer
          )}
        </div>
        
        <div className="mr-2.5 mt-0.5 text-[#aa3bff] dark:text-[#c084fc] opacity-90 transition-opacity shrink-0">
          {level === 0 ? <BookOpen size={18} /> : (isModule ? <Folder size={18} /> : <FileText size={18} />)}
        </div>

        <span className={`text-[15px] select-none text-[#08060d] dark:text-[#f3f4f6] leading-tight ${level === 0 ? 'font-bold' : 'font-medium opacity-90'}`}>
          {level === 0 ? node.name : node.title}
        </span>
      </div>

      {isOpen && isModule && (
        <div className="flex flex-col">
          {loading && (
             <div className="py-2.5 text-xs font-semibold uppercase tracking-wider text-[#6b6375] dark:text-[#9ca3af]" style={{ paddingLeft: `${padLeft + 42}px` }}>Loading...</div>
          )}
          {children && children.map(child => (
            <TreeNode 
              key={child.id} 
              node={child} 
              orgUnitId={orgUnitId || node.id} 
              level={level + 1}
              checkedTopics={checkedTopics}
              onTopicToggle={onTopicToggle}
            />
          ))}
          {children && children.length === 0 && (
             <div className="py-2.5 text-xs font-semibold uppercase tracking-wider text-[#6b6375] dark:text-[#9ca3af]" style={{ paddingLeft: `${padLeft + 42}px` }}>Empty</div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Sidebar({ 
  selectedTask,
  checkedTopics,
  onTopicToggle
}: { 
  selectedTask?: any,
  checkedTopics?: Set<number>,
  onTopicToggle?: (topic: any, checked: boolean) => void
}) {
  const [courses, setCourses] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchCourses() {
      try {
        const res = await api.get('/courses');
        setCourses(res.data);
      } catch (err) {
        console.error("Failed to load courses", err);
      } finally {
        setLoading(false);
      }
    }
    fetchCourses();
  }, []);

  if (loading) {
    return (
      <div className="animate-pulse space-y-4 pt-2">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="h-12 bg-white dark:bg-[#2e303a] border border-[#e5e4e7] dark:border-[#2e303a] rounded-xl w-full"></div>
        ))}
      </div>
    );
  }

  const displayCourses = selectedTask 
    ? courses.filter((c: any) => c.id === selectedTask.org_unit_id)
    : courses;

  return (
    <div className="flex flex-col pb-8">
      <h3 className="text-xs uppercase tracking-widest font-bold mb-3 ml-3 text-[#6b6375] dark:text-[#9ca3af]">
        {selectedTask ? 'Selected Course' : 'Fall 2026 Enrollments'}
      </h3>
      {displayCourses.map((course: any) => (
        <TreeNode 
          key={course.id} 
          node={course} 
          level={0} 
          checkedTopics={checkedTopics}
          onTopicToggle={onTopicToggle}
        />
      ))}
      {displayCourses.length === 0 && (
        <p className="text-sm font-medium text-[#6b6375] dark:text-[#9ca3af] ml-3 mt-2">No active courses found.</p>
      )}
    </div>
  );
}
