import { motion } from 'motion/react';
import { ArrowRight, Sparkles, Zap, Cloud } from 'lucide-react';
import { Button } from '../components/ui/button';
import { ImageWithFallback } from '../components/figma/ImageWithFallback';
import { useNavigate } from 'react-router';
import logoImage from '../../assets/c38e6c34bf4baff75bfaf323edf8cad56b48bc8e.png';
import designerLogo from '../../assets/bd9ff9b8b16edee7ec537992b410e819435c5bec.png';
import libraryExterior from '../../assets/40958a9cae018dddb0dfc822c93a5e35f6e2c9a1.png';
import libraryInterior from '../../assets/2c2fc22a7475d730ec8441d21514f93d4f4a6821.png';

export function HomePage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <motion.nav
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-xl border-b border-gray-100"
      >
        <div className="max-w-7xl mx-auto px-8 h-20 flex items-center justify-between">
          <img src={logoImage} alt="NaviRoom" className="h-10" />
          <Button
            onClick={() => navigate('/upload')}
            size="lg"
            className="rounded-full"
          >
            Get Started
            <ArrowRight className="ml-2 w-4 h-4" />
          </Button>
        </div>
      </motion.nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-8">
        <div className="max-w-6xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
          >
            <h2 className="text-7xl tracking-tight mb-6">
              The future of
              <br />
              reservation management
            </h2>
          </motion.div>

          <motion.p
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="text-2xl text-gray-600 mb-12 max-w-3xl mx-auto leading-relaxed"
          >
            Upload your property details once. Share everywhere.
            <br />
            Simple, powerful, and designed for modern hosts.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.6 }}
          >
            <Button
              onClick={() => navigate('/upload')}
              size="lg"
              className="h-14 px-8 text-lg rounded-full"
            >
              Start uploading
              <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
          </motion.div>
        </div>
      </section>

      {/* Feature Image */}
      <motion.section
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 1, delay: 0.8 }}
        className="px-8 pb-32"
      >
        <div className="max-w-6xl mx-auto">
          <div className="rounded-3xl overflow-hidden shadow-2xl">
            <img
              src={libraryExterior}
              alt="Modern library building"
              className="w-full h-[600px] object-cover"
            />
          </div>
        </div>
      </motion.section>

      {/* Features */}
      <section className="py-32 px-8 bg-gray-50">
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
            className="grid grid-cols-1 md:grid-cols-3 gap-12"
          >
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
                <Zap className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-3xl mb-4">Lightning Fast</h3>
              <p className="text-xl text-gray-600 leading-relaxed">
                Upload in seconds. Our intelligent system processes everything
                instantly.
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
                <Sparkles className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-3xl mb-4">AI-Powered</h3>
              <p className="text-xl text-gray-600 leading-relaxed">
                Smart suggestions help you create the perfect listing
                effortlessly.
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
                <Cloud className="w-8 h-8 text-white" />
              </div>
              <h3 className="text-3xl mb-4">Cloud Sync</h3>
              <p className="text-xl text-gray-600 leading-relaxed">
                Access your content anywhere, anytime. Always in sync.
              </p>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Secondary Feature Image */}
      <motion.section
        initial={{ opacity: 0, scale: 0.95 }}
        whileInView={{ opacity: 1, scale: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 1 }}
        className="px-8 py-32"
      >
        <div className="max-w-6xl mx-auto">
          <div className="rounded-3xl overflow-hidden shadow-2xl">
            <img
              src={libraryInterior}
              alt="Library interior"
              className="w-full h-[500px] object-cover"
            />
          </div>
        </div>
      </motion.section>

      {/* CTA Section */}
      <section className="py-32 px-8 bg-gray-50">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
          >
            <h2 className="text-6xl tracking-tight mb-8">
              Ready to get started?
            </h2>
            <p className="text-2xl text-gray-600 mb-12">
              Join thousands of hosts managing their properties with NaviRoom.
            </p>
            <Button
              onClick={() => navigate('/upload')}
              size="lg"
              className="h-14 px-8 text-lg rounded-full"
            >
              Upload your details
              <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 py-12 px-8">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <p className="text-lg text-gray-500">© 2026 NaviRoom. All rights reserved.</p>
          <div className="flex items-center gap-3">
            <span className="text-lg text-gray-500">Designed by</span>
            <img src={designerLogo} alt="Designer" className="h-8" />
          </div>
        </div>
      </footer>
    </div>
  );
}