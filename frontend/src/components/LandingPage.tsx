import React from 'react';
import { useAuth } from '../contexts/AuthContext';

const PROBLEM_CARDS = [
  { icon: '⚡', title: 'LLMs guess', desc: 'Language models generate plausible answers even when they lack grounding. Citations point to pages — not proof.' },
  { icon: '🎯', title: 'Engineers need certainty', desc: 'Pinout tables, voltage ratings, thermal limits. One wrong value can cascade into hardware failure.' },
  { icon: '📄', title: 'Documents are dense', desc: 'Datasheets, schematics, and spec sheets bury critical facts in hundreds of pages of structured data.' },
  { icon: '🔍', title: 'No audit trail', desc: "Typical AI tools can't show where an answer came from at the coordinate level. There's no way to verify." },
];

const STEPS = [
  { num: '01', title: 'Ingest', desc: 'Upload technical PDFs. Akili extracts typed facts and their exact (x, y) coordinates on each page.', tag: 'PDF → Structured Facts' },
  { num: '02', title: 'Store', desc: 'Only validated, coordinate-grounded facts enter the canonical truth store. No free-text beliefs — only structural facts.', tag: 'Units · Bijections · Grids' },
  { num: '03', title: 'Query & Verify', desc: 'Ask a question. Get an answer with proof locations — or a clear refusal. No hedging.', tag: 'Answer + Proof | REFUSE' },
];

const DIFFS = [
  { icon: '📍', title: 'Coordinate-level grounding', desc: 'Every answer tied to precise (x, y) locations — not "page 3" or a vague citation.' },
  { icon: '🛑', title: 'Deterministic refusal', desc: "If an answer can't be mathematically derived from ingested facts, Akili refuses instead of guessing." },
  { icon: '🧱', title: 'Structural canonicalization', desc: 'Raw content becomes typed objects (units, bijections, grids). Ambiguous extractions are rejected at ingestion.' },
  { icon: '✅', title: 'Show the work', desc: 'The system forces the model to show its work against a verifiable map of the truth.' },
];

const TECH_TAGS = ['Gemini', 'FastAPI', 'React', 'Typed Canonical Store', 'Z3 Solver'];

const LandingPage: React.FC = () => {
  const { signInWithGoogle, authAvailable } = useAuth();

  return (
    <div className="min-h-screen bg-[#0a0f1c] text-[#f0f2f5] overflow-x-hidden">
      {/* Nav */}
      <nav className="fixed top-0 inset-x-0 z-50 px-6 py-4 flex items-center justify-between bg-gradient-to-b from-[#0a0f1c]/95 to-transparent backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-[#0066CC] rounded-md flex items-center justify-center">
            <svg fill="none" height="18" viewBox="0 0 24 24" width="18" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="white" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
              <path d="M2 17L12 22L22 17" stroke="white" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
              <path d="M2 12L12 17L22 12" stroke="white" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
            </svg>
          </div>
          <span className="font-bold text-xl tracking-tight">Akili</span>
        </div>
        {authAvailable && (
          <button
            type="button"
            onClick={signInWithGoogle}
            className="px-5 py-2 bg-[#0066CC] text-white text-sm font-semibold rounded-md hover:shadow-[0_0_20px_rgba(0,102,204,0.35)] transition-all hover:-translate-y-0.5"
          >
            Sign In
          </button>
        )}
      </nav>

      {/* Hero */}
      <section className="min-h-screen flex flex-col justify-center px-6 md:px-12 lg:px-20 relative">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:60px_60px] pointer-events-none" />
        <div className="relative z-10 max-w-3xl">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 border border-[#0066CC]/30 rounded-full font-mono text-sm text-[#0066CC] bg-[#0066CC]/8 mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-[#2DA66A] shadow-[0_0_8px_rgba(45,166,106,0.3)]" />
            Verification Engine
          </div>
          <h1 className="text-4xl sm:text-5xl lg:text-7xl font-bold leading-[1.1] tracking-tight mb-4">
            No citations.<br />
            <span className="text-[#0066CC]">Only proof.</span>
          </h1>
          <p className="text-[#8b95a8] text-base sm:text-lg max-w-xl leading-relaxed mb-8">
            Akili is the reasoning control plane for mission-critical engineering.
            Every answer is tied to exact coordinates on your source documents — or the system refuses.
          </p>
          <div className="flex flex-col sm:flex-row gap-4">
            {authAvailable && (
              <button
                type="button"
                onClick={signInWithGoogle}
                className="px-8 py-3 bg-[#0066CC] text-white font-semibold rounded-md hover:shadow-[0_0_24px_rgba(0,102,204,0.35)] transition-all hover:-translate-y-0.5 text-center"
              >
                Get Started
              </button>
            )}
            <a
              href="#how"
              className="px-8 py-3 border border-white/12 text-[#8b95a8] font-medium rounded-md hover:border-white/30 hover:text-white transition-all text-center"
            >
              See How It Works
            </a>
          </div>
        </div>
      </section>

      {/* Problem */}
      <section className="min-h-screen flex flex-col justify-center px-6 md:px-12 lg:px-20 relative">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:60px_60px] pointer-events-none" />
        <div className="relative z-10">
          <p className="text-[#0066CC] font-bold text-sm tracking-widest mb-3">01 — THE PROBLEM</p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mb-3">"Mostly right" isn't enough.</h2>
          <p className="text-[#8b95a8] max-w-xl leading-relaxed mb-8">
            In mission-critical engineering, a wrong answer from a datasheet costs more than no answer at all.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6">
            {PROBLEM_CARDS.map((c) => (
              <div key={c.title} className="p-5 border border-white/6 rounded-lg bg-[#161d2e]">
                <div className="text-2xl mb-3">{c.icon}</div>
                <h3 className="font-semibold text-lg mb-2">{c.title}</h3>
                <p className="text-sm text-[#8b95a8] leading-relaxed">{c.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how" className="min-h-screen flex flex-col justify-center px-6 md:px-12 lg:px-20 relative">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:60px_60px] pointer-events-none" />
        <div className="relative z-10">
          <p className="text-[#0066CC] font-bold text-sm tracking-widest mb-3">02 — HOW IT WORKS</p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mb-3">Three steps to verified truth.</h2>
          <p className="text-[#8b95a8] max-w-xl leading-relaxed mb-8">
            Akili doesn't ask the AI for an answer. It forces the AI to prove the answer.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 lg:gap-6">
            {STEPS.map((s) => (
              <div key={s.num} className="p-6 border border-white/6 rounded-lg bg-[#161d2e]">
                <div className="text-4xl font-bold text-[#0066CC]/15 mb-2">{s.num}</div>
                <h3 className="font-semibold text-lg mb-2">{s.title}</h3>
                <p className="text-sm text-[#8b95a8] leading-relaxed mb-3">{s.desc}</p>
                <span className="inline-block font-mono text-xs text-[#0066CC] border border-[#0066CC]/30 px-2 py-1 rounded">
                  {s.tag}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Differentiators */}
      <section className="min-h-screen flex flex-col justify-center px-6 md:px-12 lg:px-20 relative">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:60px_60px] pointer-events-none" />
        <div className="relative z-10">
          <p className="text-[#0066CC] font-bold text-sm tracking-widest mb-3">03 — WHY AKILI</p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mb-8">
            Proof over citations.<br />Refusal over guessing.
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {DIFFS.map((d) => (
              <div key={d.title} className="flex gap-4 items-start">
                <div className="shrink-0 w-12 h-12 bg-[#0066CC]/10 border border-[#0066CC]/20 rounded-lg flex items-center justify-center text-xl">
                  {d.icon}
                </div>
                <div>
                  <h3 className="font-semibold mb-1">{d.title}</h3>
                  <p className="text-sm text-[#8b95a8] leading-relaxed">{d.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="min-h-screen flex flex-col justify-center items-center text-center px-6 md:px-12 lg:px-20 relative">
        <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:60px_60px] pointer-events-none" />
        <div className="relative z-10 flex flex-col items-center">
          <p className="text-[#0066CC] font-bold text-sm tracking-widest mb-3">04 — GET STARTED</p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mb-3 max-w-xl">
            Where AI shows its work.
          </h2>
          <p className="text-[#8b95a8] max-w-xl leading-relaxed mb-8">
            Built for engineering teams in aerospace, medical devices, automotive, and defense who need to trust answers from documentation.
          </p>
          {authAvailable && (
            <button
              type="button"
              onClick={signInWithGoogle}
              className="px-8 py-3 bg-[#0066CC] text-white font-semibold rounded-md hover:shadow-[0_0_24px_rgba(0,102,204,0.35)] transition-all hover:-translate-y-0.5 mb-8"
            >
              Get Started
            </button>
          )}
          <div className="flex flex-wrap justify-center gap-2">
            {TECH_TAGS.map((tag) => (
              <span key={tag} className="font-mono text-xs px-3 py-1.5 border border-white/8 rounded text-[#8b95a8]">
                {tag}
              </span>
            ))}
          </div>
        </div>
        <footer className="absolute bottom-0 inset-x-0 px-6 py-4 flex justify-between items-center">
          <p className="font-mono text-xs text-white/25">&copy; 2026 Akili</p>
          <p className="font-mono text-xs text-white/25">No citations. Only proof.</p>
        </footer>
      </section>
    </div>
  );
};

export default LandingPage;
