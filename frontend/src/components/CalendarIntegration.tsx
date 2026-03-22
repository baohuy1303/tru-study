import React, { useState } from 'react';
import { SignInButton, useSession } from '@clerk/clerk-react';
import api from '../lib/api'; 

interface CalendarIntegrationProps {
  onSuccess?: () => void;
}

const CalendarIntegration: React.FC<CalendarIntegrationProps> = ({ onSuccess }) => {
  const { session, isLoaded, isSignedIn } = useSession();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  const handleAddDummyEvent = async () => {
    if (!session) {
      setMessage("You must be signed in to add an event.");
      return;
    }

    setLoading(true);
    setMessage('');

    try {
      // Get the clerk session JWT to pass as a Bearer token
      const token = await session.getToken();
      
      // Calculate start and end times in ISO 8601 (24 hours from now)
      const start = new Date(Date.now() + 24 * 60 * 60 * 1000);
      const end = new Date(start.getTime() + 60 * 60 * 1000); // 1 hour duration

      const response = await api.post(
        '/add-event',
        {
          summary: "Study Session: Hackathon Prep",
          description: "This is a test event created by the TruStudy integration.",
          start_time: start.toISOString(),
          end_time: end.toISOString()
        },
        {
          headers: {
            'X-Clerk-Auth': `Bearer ${token}`
          }
        }
      );

      if (response.data?.status === 'success') {
        setMessage(`Event added! Check your calendar.`);
        onSuccess?.();
      } else {
        setMessage('Unexpected response from server.');
      }
    } catch (err: any) {
      console.error(err);
      setMessage(err.response?.data?.detail || "Failed to add event. Did you grant Calendar permissions during login?");
    } finally {
      setLoading(false);
    }
  };

  if (!isLoaded) return <div>Loading...</div>;

  return (
    <div className="p-6 border border-[#e5e4e7] dark:border-[#2e303a] rounded-2xl bg-white dark:bg-[#1f2028] max-w-sm">
      <h3 className="text-xl font-bold mb-4 text-[#08060d] dark:text-[#f3f4f6]">Google Calendar Setup</h3>
      
      {!isSignedIn ? (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-[#6b6375] dark:text-[#9ca3af]">
            Sign in with Google to allow us to add study sessions to your personal calendar.
          </p>
          {/* Default Clerk SignInButton */}
          <SignInButton mode="modal">
            <button className="py-2 px-4 bg-[#aa3bff] hover:bg-[#902ee6] text-white rounded-lg font-medium transition-colors cursor-pointer">
              Sign In with Google
            </button>
          </SignInButton>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-[#6b6375] dark:text-[#9ca3af]">
            You're signed in! We can now add events to your Google Calendar.
          </p>
          
          <button 
            onClick={handleAddDummyEvent}
            disabled={loading}
            className={`py-2 px-4 rounded-lg font-medium transition-colors text-white ${
              loading ? 'bg-gray-400 cursor-not-allowed' : 'bg-[#aa3bff] hover:bg-[#902ee6] cursor-pointer'
            }`}
          >
            {loading ? 'Adding Event...' : 'Add Dummy Event'}
          </button>
          
          {message && (
            <p className={`text-sm mt-2 ${message.includes('added') ? 'text-green-500' : 'text-rose-500'}`}>
              {message}
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default CalendarIntegration;
