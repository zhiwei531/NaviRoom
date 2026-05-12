import { motion } from 'motion/react';
import { useNavigate } from 'react-router';
import { ArrowRight, Upload, Sparkles, Share2, CheckCircle } from 'lucide-react';
import { Button } from '../components/ui/button';
import { TopBar } from '../components/TopBar';
import logoImage from 'figma:asset/c38e6c34bf4baff75bfaf323edf8cad56b48bc8e.png';

const steps = [
  {
    number: '01',
    icon: Upload,
    title: 'Upload your property',
    description:
      'Start by adding high-quality photos of your space and a detailed description. Our system accepts all major image formats and guides you through each field.',
  },
  {
    number: '02',
    icon: Sparkles,
    title: 'AI enhances your listing',
    description:
      "NaviRoom's AI engine automatically refines your description, suggests the best tags, and optimises your images for maximum visual impact across all platforms.",
  },
  {
    number: '03',
    icon: Share2,
    title: 'Publish & share instantly',
    description:
      'With one click your listing goes live. Share a clean, branded link with guests or embed it directly into your own website.',
  },
  {
    number: '04',
    icon: CheckCircle,
    title: 'Manage reservations',
    description:
      'Track bookings, respond to guest inquiries, and manage availability all from a single, intuitive dashboard — no spreadsheets required.',
  },
];

const faqs = [
  {
    q: 'How many photos can I upload per listing?',
    a: 'You can upload up to 30 high-resolution photos per property. We recommend at least 8 photos to give guests a comprehensive view of your space.',
  },
  {
    q: 'Is there a free tier?',
    a: 'Yes — NaviRoom offers a free plan that lets you create up to 3 active listings with full AI features included. Upgrade anytime for unlimited listings and analytics.',
  },
  {
    q: 'Can I update my listing after publishing?',
    a: 'Absolutely. All edits are reflected in real time across every channel your listing appears on.',
  },
  {
    q: 'What file formats are supported?',
    a: 'We support JPEG, PNG, WebP, and HEIC. Maximum file size per image is 20 MB.',
  },
];

export function TutorialPage() {
  const navigate = useNavigate();

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
          <Button onClick={() => navigate('/upload')} size="lg" className="rounded-full">
            Get Started
            <ArrowRight className="ml-2 w-4 h-4" />
          </Button>
        </div>
      </motion.nav>

      {/* Hero */}
      <section className="pt-40 pb-32 px-8">
        <div className="max-w-6xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
          >
            <h1 className="text-7xl tracking-tight mb-8">
              Get up and running
              <br />
              in minutes
            </h1>
            <p className="text-2xl text-gray-600 leading-relaxed max-w-3xl mx-auto">
              NaviRoom is designed to be effortless. Follow these four steps and
              your property will be live before your next cup of coffee.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Steps */}
      <section className="py-32 px-8">
        <div className="max-w-6xl mx-auto">
          <div className="space-y-8">
            {steps.map((step, i) => {
              const Icon = step.icon;
              return (
                <motion.div
                  key={step.number}
                  initial={{ opacity: 0, x: -30 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.6, delay: i * 0.1 }}
                  className="flex items-start gap-12 p-12 rounded-3xl bg-gray-50 hover:bg-gray-100/70 transition-colors duration-300"
                >
                  <div className="flex-shrink-0 flex flex-col items-center gap-6">
                    <span className="text-6xl text-gray-200 select-none leading-none">
                      {step.number}
                    </span>
                    <div className="w-16 h-16 bg-blue-600 rounded-2xl flex items-center justify-center">
                      <Icon className="w-8 h-8 text-white" />
                    </div>
                  </div>
                  <div className="pt-2">
                    <h3 className="text-4xl mb-4 tracking-tight">{step.title}</h3>
                    <p className="text-xl text-gray-600 leading-relaxed max-w-3xl">
                      {step.description}
                    </p>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="py-32 px-8 bg-gray-50">
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
          >
            <h2 className="text-6xl tracking-tight mb-20 text-center">
              Frequently asked questions
            </h2>
            <div className="space-y-6">
              {faqs.map((faq, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.5, delay: i * 0.08 }}
                  className="bg-white rounded-3xl p-10"
                >
                  <p className="text-2xl mb-4">{faq.q}</p>
                  <p className="text-xl text-gray-600 leading-relaxed">{faq.a}</p>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-32 px-8">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
          >
            <h2 className="text-6xl tracking-tight mb-8">Ready to try it?</h2>
            <p className="text-2xl text-gray-600 mb-12 max-w-3xl mx-auto leading-relaxed">
              Create your first listing for free — no credit card required.
            </p>
            <Button
              onClick={() => navigate('/upload')}
              size="lg"
              className="h-14 px-8 text-lg rounded-full"
            >
              Upload your space
              <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 py-10 px-8">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <p className="text-lg text-gray-400">© 2026 NaviRoom. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}