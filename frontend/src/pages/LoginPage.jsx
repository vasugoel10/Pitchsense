import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, Lock, ArrowRight } from 'lucide-react';
import { apiFetch } from '../utils/api';

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  const [error, setError] = useState('');

  const handleAuth = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    
    const endpoint = isRegistering ? '/api/register/' : '/api/login/';
    
    try {
      const data = await apiFetch(endpoint, {
        method: 'POST',
        body: JSON.stringify({
          username: email,
          password: password,
        })
      });
      
      if (data.status === 'success') {
        if (data.user.is_admin) {
          sessionStorage.setItem('pitchsense_user_role', 'admin');
          navigate('/admin-dashboard');
        } else {
          sessionStorage.setItem('pitchsense_user_role', 'customer');
          navigate('/debate');
        }
      } else {
        setError(data.message || 'Authentication failed');
      }
    } catch (err) {
      setError('Network error connecting to server.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-[#0a0a0f] relative overflow-hidden font-sans">
      {/* Background Effects */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-indigo-600/20 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] rounded-full bg-purple-600/20 blur-[120px] pointer-events-none" />

      <div className="w-full max-w-md p-8 relative z-10">
        
        {/* Logo */}
        <div className="flex flex-col items-center mb-10">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-[0_0_30px_rgba(99,102,241,0.5)] mb-4 animate-in zoom-in duration-500">
            <span className="text-white text-4xl font-black leading-none pb-1">P</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2 animate-in fade-in slide-in-from-bottom-4 duration-700">
            Pitch<span className="text-indigo-400 font-extrabold">Sense</span>
          </h1>
          <p className="text-gray-400 text-sm font-medium animate-in fade-in slide-in-from-bottom-4 duration-700 delay-100">
            Sign in to enter the arena
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-[#111118]/80 backdrop-blur-xl border border-white/10 p-8 rounded-3xl shadow-2xl animate-in slide-in-from-bottom-8 fade-in duration-700 delay-200">
          
          <form onSubmit={handleAuth} className="space-y-5">
            {error && (
              <div className="bg-red-500/10 border border-red-500/50 text-red-400 text-sm p-3 rounded-xl flex items-center justify-center animate-in fade-in">
                {error}
              </div>
            )}
            
            {/* Email Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-gray-400 uppercase tracking-wider pl-1">Email</label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-gray-500 group-focus-within:text-indigo-400 transition-colors">
                  <Mail size={18} />
                </div>
                <input 
                  type="email" 
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-black/40 border border-white/10 focus:border-indigo-500/50 focus:bg-black/60 rounded-xl py-3 pl-11 pr-4 text-white text-sm outline-none transition-all placeholder:text-gray-600"
                  placeholder="name@startup.com"
                  required
                />
              </div>
            </div>

            {/* Password Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-bold text-gray-400 uppercase tracking-wider pl-1">Password</label>
              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none text-gray-500 group-focus-within:text-indigo-400 transition-colors">
                  <Lock size={18} />
                </div>
                <input 
                  type="password" 
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-black/40 border border-white/10 focus:border-indigo-500/50 focus:bg-black/60 rounded-xl py-3 pl-11 pr-4 text-white text-sm outline-none transition-all placeholder:text-gray-600"
                  placeholder="••••••••"
                  required
                />
              </div>
            </div>

            {/* Submit Button */}
            <button 
              type="submit"
              disabled={isLoading || !email || !password}
              className={`w-full flex items-center justify-center gap-2 py-3.5 mt-4 rounded-xl font-bold tracking-wide transition-all
                ${isLoading || !email || !password 
                  ? 'bg-gray-800 text-gray-500 cursor-not-allowed' 
                  : 'bg-white hover:bg-gray-100 text-black shadow-[0_0_20px_rgba(255,255,255,0.2)]'
                }`}
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  {isRegistering ? 'Create Account' : 'Sign In'}
                  <ArrowRight size={18} />
                </>
              )}
            </button>
            
            {/* Toggle Login/Register */}
            <div className="text-center mt-4">
              <button 
                type="button" 
                onClick={() => setIsRegistering(!isRegistering)}
                className="text-xs text-gray-400 hover:text-white transition-colors"
              >
                {isRegistering ? 'Already have an account? Sign In' : 'Need an account? Register'}
              </button>
            </div>
          </form>

        </div>
        
        {/* Footer */}
        <p className="text-center text-xs font-medium text-gray-600 mt-8 animate-in fade-in duration-1000 delay-500">
          Protected by AES-256 Encryption &bull; PitchSense OS
        </p>
      </div>
    </div>
  );
}
