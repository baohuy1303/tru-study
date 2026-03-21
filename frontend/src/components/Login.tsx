import { useState } from 'react';
import api from '../lib/api';

export default function Login({ onLoginSuccess }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await api.post('/auth/login', { username, password });
      const { token, user_id, first_name, last_name } = response.data;
      
      // Save token and pass user data up
      localStorage.setItem('bs_token', token);
      onLoginSuccess({ user_id, first_name, last_name, token });
    } catch (err) {
      setError(
        err.response?.data?.detail || 'Failed to login. Please check your credentials.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f4f3ec] dark:bg-[#16171d]">
      <div className="bg-white dark:bg-[#1f2028] p-8 rounded-lg shadow-[rgba(0,0,0,0.1)_0_10px_15px_-3px] dark:shadow-[rgba(0,0,0,0.4)_0_10px_15px_-3px] w-full max-w-md border border-[#e5e4e7] dark:border-[#2e303a]">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-semibold tracking-tight text-[#08060d] dark:text-[#f3f4f6] mb-2">TruStudy 🎓</h1>
          <p className="text-[#6b6375] dark:text-[#9ca3af]">Sign in with your Truman credentials</p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-md text-red-600 dark:text-red-400 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-[#08060d] dark:text-[#f3f4f6] mb-1">
              Truman Username
            </label>
            <input
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-2 bg-[#f4f3ec] dark:bg-[#16171d] border border-[#e5e4e7] dark:border-[#2e303a] rounded-md focus:outline-none focus:ring-2 focus:ring-[#aa3bff] dark:focus:ring-[#c084fc] text-[#08060d] dark:text-[#f3f4f6] transition-shadow"
              placeholder="e.g., jdoe"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[#08060d] dark:text-[#f3f4f6] mb-1">
              Password
            </label>
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 bg-[#f4f3ec] dark:bg-[#16171d] border border-[#e5e4e7] dark:border-[#2e303a] rounded-md focus:outline-none focus:ring-2 focus:ring-[#aa3bff] dark:focus:ring-[#c084fc] text-[#08060d] dark:text-[#f3f4f6] transition-shadow"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 px-4 bg-[#aa3bff] hover:bg-[#9922ff] dark:bg-[#c084fc] dark:hover:bg-[#a855f7] text-white dark:text-[#08060d] font-semibold rounded-md shadow-md transition-colors disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center"
          >
            {loading ? (
              <svg className="animate-spin h-5 w-5 mr-2 text-white dark:text-[#08060d]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            ) : (
              'Sign In'
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
