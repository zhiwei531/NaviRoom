import { motion } from 'motion/react';
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { ArrowRight, Eye, EyeOff } from 'lucide-react';
import { Button } from '../components/ui/button';
import { TopBar } from '../components/TopBar';
import { useAuth } from '../context/AuthContext';
import logoImage from 'figma:asset/c38e6c34bf4baff75bfaf323edf8cad56b48bc8e.png';

export function SignInPage() {
  const navigate = useNavigate();
  const { signIn, signUp } = useAuth();
  const [isSignUp, setIsSignUp] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [form, setForm] = useState({ username: '', password: '' });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      if (isSignUp) {
        await signUp(form.username, form.password);
      } else {
        await signIn(form.username, form.password);
      }
      navigate('/upload');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setSubmitting(false);
    }
  };

  const handleChange = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
  };

  return (
    <div className="min-h-screen bg-white">
      <TopBar />

      {/* Nav */}
      <motion.nav
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="fixed left-0 right-0 z-50 bg-white/80 backdrop-blur-xl border-b border-gray-100"
        style={{ top: '36px' }}
      >
        <div className="max-w-7xl mx-auto px-8 h-20 flex items-center justify-between">
          <button onClick={() => navigate('/')} className="hover:opacity-70 transition-opacity">
            <img src={logoImage} alt="NaviRoom" className="h-10" />
          </button>
          <button
            onClick={() => setIsSignUp((v) => !v)}
            className="text-sm text-gray-500 hover:text-gray-900 transition-colors"
          >
            {isSignUp ? 'Already have an account? Sign in' : "Don't have an account? Sign up"}
          </button>
        </div>
      </motion.nav>

      {/* Main */}
      <div className="min-h-screen flex items-center justify-center px-8 pt-32 pb-20">
        <motion.div
          key={isSignUp ? 'signup' : 'signin'}
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="w-full max-w-xl"
        >
          {/* Card */}
          <div className="bg-white border border-gray-100 rounded-3xl shadow-xl p-16">
            {/* Header */}
            <div className="text-center mb-12">
              <h1 className="text-5xl tracking-tight mb-4">
                {isSignUp ? 'Create account' : 'Welcome back'}
              </h1>
              <p className="text-xl text-gray-600">
                {isSignUp
                  ? 'Start managing your properties today'
                  : 'Sign in to your NaviRoom account'}
              </p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-base text-gray-600 mb-3 ml-1">Username</label>
                <input
                  type="text"
                  value={form.username}
                  onChange={handleChange('username')}
                  placeholder="your_username"
                  required
                  className="w-full border border-gray-200 rounded-2xl px-6 py-5 text-lg focus:outline-none focus:border-blue-500 transition-colors bg-gray-50 hover:bg-white"
                />
              </div>

              <div>
                <label className="block text-base text-gray-600 mb-3 ml-1">Password</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={form.password}
                    onChange={handleChange('password')}
                    placeholder="••••••••"
                    required
                    className="w-full border border-gray-200 rounded-2xl px-6 py-5 pr-14 text-lg focus:outline-none focus:border-blue-500 transition-colors bg-gray-50 hover:bg-white"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              {error && <p className="text-sm text-red-500">{error}</p>}

              <div className="pt-4">
                <Button
                  type="submit"
                  size="lg"
                  className="w-full h-16 text-lg rounded-2xl"
                  disabled={submitting}
                >
                  {submitting ? (
                    'Processing...'
                  ) : isSignUp ? (
                    <>
                      Create account
                      <ArrowRight className="ml-2 w-5 h-5" />
                    </>
                  ) : (
                    <>
                      Sign in
                      <ArrowRight className="ml-2 w-5 h-5" />
                    </>
                  )}
                </Button>
              </div>
            </form>

            {/* Switch mode */}
            <p className="text-center text-base text-gray-500 mt-10">
              {isSignUp ? 'Already have an account? ' : "Don't have an account? "}
              <button
                type="button"
                onClick={() => setIsSignUp((v) => !v)}
                className="text-blue-600 hover:underline"
              >
                {isSignUp ? 'Sign in' : 'Sign up'}
              </button>
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
