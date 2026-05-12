import { useNavigate, useLocation } from 'react-router';
import { motion } from 'motion/react';

const links = [
  { label: 'Home', path: '/' },
  { label: 'Upload', path: '/upload' },
  { label: 'Tutorial', path: '/tutorial' },
  { label: 'About Us', path: '/about' },
];

export function TopBar() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="fixed top-0 left-0 right-0 z-[60] bg-gray-50/95 backdrop-blur-sm border-b border-gray-200/60"
      style={{ height: '36px' }}
    >
      <div className="max-w-7xl mx-auto px-8 h-full flex items-center justify-between">
        <span className="text-xs text-gray-600 tracking-wide hidden sm:block">
          Welcome to NaviRoom — free & open access
        </span>

        <nav className="flex items-center gap-1 ml-auto">
          {links.map((link, i) => {
            const isActive = location.pathname === link.path;
            return (
              <span key={link.path} className="flex items-center">
                {i > 0 && (
                  <span className="mx-2 text-gray-300 text-xs select-none">·</span>
                )}
                <button
                  onClick={() => navigate(link.path)}
                  className={`text-xs px-1 py-0.5 transition-colors duration-200 rounded ${
                    isActive
                      ? 'text-blue-600'
                      : 'text-gray-500 hover:text-gray-900'
                  }`}
                >
                  {link.label}
                </button>
              </span>
            );
          })}
        </nav>
      </div>
    </motion.div>
  );
}