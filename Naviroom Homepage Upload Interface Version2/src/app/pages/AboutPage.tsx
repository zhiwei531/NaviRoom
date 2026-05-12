import { motion } from 'motion/react';
import { useNavigate } from 'react-router';
import { ArrowRight } from 'lucide-react';
import { Button } from '../components/ui/button';
import { TopBar } from '../components/TopBar';
import logoImage from 'figma:asset/c38e6c34bf4baff75bfaf323edf8cad56b48bc8e.png';
import designerLogo from 'figma:asset/bd9ff9b8b16edee7ec537992b410e819435c5bec.png';

const values = [
  {
    title: 'Clarity first',
    description:
      'Every feature we build starts with a single question: does this make the host\'s life simpler? If not, we cut it.',
  },
  {
    title: 'Design that lasts',
    description:
      'We believe software should feel calm and considered — not loud and cluttered. Good design stands the test of time.',
  },
  {
    title: 'Built on trust',
    description:
      'Your data and your guests\' data are treated with the utmost care. We will never sell, share, or exploit it.',
  },
];

const team = [
  { name: 'Aria Chen', role: 'Co-founder & CEO' },
  { name: 'Marcus Yuen', role: 'Co-founder & CTO' },
  { name: 'Sofia Rossi', role: 'Head of Design' },
  { name: 'Daniel Park', role: 'Head of Product' },
];

export function AboutPage() {
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
        <div className="max-w-6xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
          >
            <h1 className="text-7xl tracking-tight mb-8">
              Built by hosts,
              <br />
              for hosts.
            </h1>
            <p className="text-2xl text-gray-600 leading-relaxed max-w-3xl">
              NaviRoom was founded in 2024 after its founders spent years
              wrestling with clunky property management tools that tried to do
              everything and ended up doing nothing well. We set out to build
              the opposite: one focused, beautiful product.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Divider image strip */}
      <motion.div
        initial={{ opacity: 0, scaleX: 0.9 }}
        whileInView={{ opacity: 1, scaleX: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 0.8 }}
        className="px-8 pb-32"
      >
        <div className="max-w-6xl mx-auto rounded-3xl overflow-hidden bg-gray-100 h-80 flex items-center justify-center">
          <p className="text-gray-400 text-2xl">San Francisco · 2024</p>
        </div>
      </motion.div>

      {/* Mission */}
      <section className="py-32 px-8 bg-gray-50">
        <div className="max-w-5xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8 }}
          >
            <h2 className="text-6xl tracking-tight mb-10">Our mission</h2>
            <p className="text-2xl text-gray-600 leading-relaxed">
              To make listing and managing a property feel as effortless as
              sending a message — so hosts can spend less time on admin and more
              time creating exceptional guest experiences.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Values */}
      <section className="py-32 px-8">
        <div className="max-w-6xl mx-auto">
          <motion.h2
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="text-6xl tracking-tight mb-16"
          >
            What we believe
          </motion.h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {values.map((v, i) => (
              <motion.div
                key={v.title}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: i * 0.12 }}
                className="bg-gray-50 rounded-3xl p-12"
              >
                <h3 className="text-3xl mb-6 tracking-tight">{v.title}</h3>
                <p className="text-xl text-gray-600 leading-relaxed">{v.description}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Team */}
      <section className="py-32 px-8 bg-gray-50">
        <div className="max-w-6xl mx-auto">
          <motion.h2
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            className="text-6xl tracking-tight mb-16 text-center"
          >
            The team
          </motion.h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {team.map((member, i) => (
              <motion.div
                key={member.name}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.08 }}
                className="bg-white rounded-3xl p-10 text-center"
              >
                <div className="w-20 h-20 rounded-full bg-blue-100 mx-auto mb-6 flex items-center justify-center">
                  <span className="text-blue-600 text-2xl">
                    {member.name.charAt(0)}
                  </span>
                </div>
                <p className="text-xl mb-2">{member.name}</p>
                <p className="text-base text-gray-500">{member.role}</p>
              </motion.div>
            ))}
          </div>
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
            <h2 className="text-6xl tracking-tight mb-8">Come build with us</h2>
            <p className="text-2xl text-gray-600 mb-12 leading-relaxed">
              We are always looking for thoughtful people who care about craft.
            </p>
            <Button
              onClick={() => navigate('/signin')}
              size="lg"
              className="h-14 px-8 text-lg rounded-full"
            >
              Create an account
              <ArrowRight className="ml-2 w-5 h-5" />
            </Button>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-100 py-12 px-8">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <p className="text-lg text-gray-400">© 2026 NaviRoom. All rights reserved.</p>
          <div className="flex items-center gap-3">
            <span className="text-lg text-gray-400">Designed by</span>
            <img src={designerLogo} alt="Designer" className="h-8" />
          </div>
        </div>
      </footer>
    </div>
  );
}