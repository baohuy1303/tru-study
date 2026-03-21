import { useState } from 'react';
import api from '../lib/api';

export default function Login({ onLoginSuccess }: { onLoginSuccess: (data: any) => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await api.post('/auth/login', { username, password });
      const { token, user_id, first_name, last_name } = response.data;
      
      localStorage.setItem('bs_token', token);
      onLoginSuccess({ user_id, first_name, last_name, token });
    } catch (err: any) {
      setError(
        err.response?.data?.detail || 'Failed to login. Please check your credentials.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center bg-[#09090b] overflow-hidden selection:bg-[#aa3bff]/30">
      
      {/* Dynamic Background Glowing Orbs */}
      <div className="absolute top-[-15%] left-[-15%] w-[60%] h-[60%] bg-gradient-to-br from-[#aa3bff]/25 to-transparent rounded-full blur-[120px] pointer-events-none mix-blend-screen" />
      <div className="absolute bottom-[-15%] right-[-15%] w-[60%] h-[60%] bg-gradient-to-tl from-[#c084fc]/20 to-transparent rounded-full blur-[120px] pointer-events-none mix-blend-screen" />
      <div className="absolute top-[35%] left-[55%] w-[35%] h-[35%] bg-gradient-to-tl from-[#5b21b6]/20 to-transparent rounded-full blur-[100px] pointer-events-none mix-blend-screen" />
      
      {/* Glassmorphic Login Card */}
      <div className="relative z-10 w-full max-w-[440px] px-6">
        <div className="bg-white/[0.03] backdrop-blur-2xl border border-white/10 p-10 sm:p-12 rounded-[2.5rem] shadow-[0_8px_32px_0_rgba(0,0,0,0.4)] flex flex-col items-center group/card transition-all duration-500 hover:border-white/20 hover:bg-white/[0.05]">
          
          <div className="text-center mb-10 w-full">
            <div className="inline-flex items-center justify-center p-3.5 bg-white/5 rounded-2xl border border-white/10 shadow-inner mb-6 ring-1 ring-white/5 transition-transform duration-500 group-hover/card:scale-105 group-hover/card:bg-white/10">
              <span className="text-4xl leading-none">🎓</span>
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-white mb-3 font-sans">
              TruStudy
            </h1>
            <p className="text-[#a1a1aa] text-sm font-medium tracking-wide uppercase">
              Welcome back
            </p>
          </div>

          {error && (
            <div className="w-full mb-8 p-4 bg-red-500/10 border border-red-500/20 rounded-2xl text-red-400 text-sm font-medium text-center shadow-inner">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="w-full space-y-6">
            <div className="space-y-2">
              <label className="block text-xs font-bold uppercase tracking-widest text-[#a1a1aa] ml-2">
                Username
              </label>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-5 py-4 bg-black/30 border border-white/10 rounded-2xl focus:outline-none focus:ring-2 focus:ring-[#aa3bff]/60 focus:border-[#aa3bff]/60 focus:bg-white/5 text-white placeholder-white/20 transition-all duration-300 font-medium text-[15px] shadow-inner"
                placeholder="e.g., jdoe"
              />
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-bold uppercase tracking-widest text-[#a1a1aa] ml-2">
                Password
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-5 py-4 bg-black/30 border border-white/10 rounded-2xl focus:outline-none focus:ring-2 focus:ring-[#aa3bff]/60 focus:border-[#aa3bff]/60 focus:bg-white/5 text-white placeholder-white/20 transition-all duration-300 font-medium text-[15px] shadow-inner"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-4 px-4 bg-gradient-to-r from-[#aa3bff] to-[#c084fc] hover:from-[#9922ff] hover:to-[#a855f7] text-white font-bold tracking-widest uppercase text-sm rounded-2xl shadow-[0_0_20px_rgba(170,59,255,0.2)] hover:shadow-[0_0_35px_rgba(170,59,255,0.4)] hover:-translate-y-[2px] active:translate-y-0 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 flex items-center justify-center group"
            >
              {loading ? (
                <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              ) : (
                <>
                  <span className="mt-0.5">Sign In to Brightspace</span>
                  <svg className="w-5 h-5 ml-2.5 opacity-70 group-hover:translate-x-1.5 group-hover:opacity-100 transition-all duration-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                  </svg>
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
