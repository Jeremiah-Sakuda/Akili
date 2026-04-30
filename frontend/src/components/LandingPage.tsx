import React from 'react';
import { useAuth } from '../contexts/AuthContext';
import { useScrollReveal } from '../hooks/useReveal';
import { BenchmarkTable, DEFAULT_BENCHMARK_DATA } from './BenchmarkTable';

function RevealSection({ children, className = '', id, ariaLabel }: {
  children: React.ReactNode; className?: string; id?: string; ariaLabel?: string;
}) {
  const { ref, visible } = useScrollReveal();
  return (
    <section
      id={id}
      ref={ref}
      aria-label={ariaLabel}
      className={`${className} transition-all duration-700 ease-out ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-6'}`}
    >
      {children}
    </section>
  );
}

/* ─── Grid background reused across sections ─── */
const GridBg = () => (
  <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:60px_60px] pointer-events-none" />
);

/* ─── Data ─── */
const PROBLEM_CARDS = [
  { icon: '⚡', title: 'LLMs guess', desc: 'Language models generate plausible answers even when they lack grounding. Citations point to pages — not proof.' },
  { icon: '🎯', title: 'Engineers need certainty', desc: 'Pinout tables, voltage ratings, thermal limits. One wrong value can cascade into hardware failure.' },
  { icon: '📄', title: 'Documents are dense', desc: 'Datasheets, schematics, and spec sheets bury critical facts in hundreds of pages of structured data.' },
  { icon: '🔍', title: 'No audit trail', desc: "Typical AI tools can't show where an answer came from at the coordinate level. There's no way to verify." },
];

const STEPS = [
  { num: '01', title: 'Ingest', desc: 'Upload technical PDFs. Akili extracts typed facts and their exact (x, y) coordinates on each page using Gemini multimodal AI.', tag: 'PDF → Structured Facts' },
  { num: '02', title: 'Canonicalize', desc: 'Only validated, coordinate-grounded facts enter the canonical truth store. No free-text beliefs — only typed structural objects.', tag: 'Units · Bijections · Grids' },
  { num: '03', title: 'Verify', desc: 'Ask a question. 30 verification rules attempt to derive the answer from canonical facts. You get proof coordinates — or a deterministic refusal.', tag: 'Answer + Proof | REFUSE' },
];

const DIFFS = [
  { icon: '📍', title: 'Coordinate-level grounding', desc: 'Every answer tied to precise (x, y) locations on a specific page — not "page 3" or a vague citation.' },
  { icon: '🛑', title: 'Deterministic refusal', desc: "If an answer can't be mathematically derived from ingested facts, Akili refuses instead of guessing." },
  { icon: '🧱', title: 'Structural canonicalization', desc: 'Raw content becomes typed objects (units, bijections, grids). Ambiguous extractions are rejected at ingestion.' },
  { icon: '✅', title: 'Proof chains', desc: 'Every answer includes the rule that derived it, the canonical source, and the exact document coordinates.' },
];

const CANONICAL_TYPES = [
  { name: 'Unit', example: 'VCC = 3.3 V', desc: 'A single named value with optional unit of measure, extracted from tables or text.' },
  { name: 'Bijection', example: 'Pin 1 → VCC', desc: 'A 1-to-1 mapping between two sets, such as pin numbers to signal names.' },
  { name: 'Grid', example: '4×3 parameter table', desc: 'Structured table data — rows, columns, and cell values with coordinates per cell.' },
  { name: 'Range', example: '-40 / 25 / 85 °C', desc: 'A min/typ/max specification for a parameter, with optional test conditions.' },
  { name: 'ConditionalUnit', example: 'IOH = 4 mA @ VCC = 3.3 V', desc: 'A value that depends on one or more conditions being true.' },
];

const TIERS = [
  { tier: 'VERIFIED', threshold: '≥ 85%', color: '#2DA66A', desc: 'Fact fully derived from canonical objects. Proof coordinates provided.', icon: 'verified' },
  { tier: 'REVIEW', threshold: '50 – 85%', color: '#D4A017', desc: 'Partial match found. Answer returned with a review flag for human confirmation.', icon: 'rate_review' },
  { tier: 'REFUSED', threshold: '< 50%', color: '#D44040', desc: 'No derivation path exists. System refuses rather than guessing.', icon: 'block' },
];

const DERIVED_QUERIES = [
  { name: 'Power', formula: 'P = V × I', desc: 'Computes power dissipation from voltage and current facts.' },
  { name: 'Thermal', formula: 'Tj = Ta + (P × θJA)', desc: 'Derives junction temperature from ambient, power, and thermal resistance.' },
  { name: 'Voltage margin', formula: '(Vabs − Vop) / Vabs', desc: 'Calculates percentage headroom between operating and absolute maximum voltage.' },
  { name: 'Current budget', formula: 'Budget = Imax − ΣI', desc: 'Sums current consumers to check against the supply limit.' },
];

const STATS = [
  { value: '30', label: 'Verification rules' },
  { value: '5', label: 'Canonical types' },
  { value: '3', label: 'Confidence tiers' },
  { value: '4', label: 'Derived queries' },
];

const INDUSTRIES = ['Aerospace', 'Medical Devices', 'Automotive', 'Defense', 'Semiconductor', 'Industrial'];

const TECH_TAGS = ['Gemini 3 Flash', 'FastAPI', 'React 19', 'Typed Canonical Store', 'Z3 Solver', 'Firebase Auth'];

/* ─── Mock query demo data ─── */
const MOCK_QUESTION = 'What is the absolute maximum voltage?';
const MOCK_RESPONSE = {
  answer: '7.0 V',
  source: 'u_abs_vmax',
  rule: 'absolute_max_voltage (priority 200)',
  coords: '(0.45, 0.32) page 1',
  confidence: '86%',
  tier: 'VERIFIED',
};

/* ─── Component ─── */
const LandingPage: React.FC = () => {
  const { signInWithGoogle, authAvailable } = useAuth();

  return (
    <div className="min-h-screen bg-[#0a0f1c] text-[#f0f2f5] overflow-x-hidden">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-[60] focus:px-4 focus:py-2 focus:bg-[#0066CC] focus:text-white focus:rounded-md">
        Skip to main content
      </a>

      {/* ─── Nav ─── */}
      <nav aria-label="Landing page navigation" className="fixed top-0 inset-x-0 z-50 px-6 py-4 flex items-center justify-between bg-gradient-to-b from-[#0a0f1c]/95 to-transparent backdrop-blur-sm">
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
        <div className="flex items-center gap-6">
          <a href="#how" className="hidden sm:block text-sm text-[#8b95a8] hover:text-white transition-colors">How it works</a>
          <a href="#types" className="hidden sm:block text-sm text-[#8b95a8] hover:text-white transition-colors">Architecture</a>
          <a href="#demo" className="hidden sm:block text-sm text-[#8b95a8] hover:text-white transition-colors">Demo</a>
          {authAvailable && (
            <button
              type="button"
              onClick={signInWithGoogle}
              className="px-5 py-2 bg-[#0066CC] text-white text-sm font-semibold rounded-md hover:shadow-[0_0_20px_rgba(0,102,204,0.35)] transition-all hover:-translate-y-0.5"
            >
              Sign In
            </button>
          )}
        </div>
      </nav>

      {/* ─── Hero ─── */}
      <section id="main-content" aria-label="Hero" className="min-h-screen flex flex-col justify-center px-6 md:px-12 lg:px-20 pt-20 relative">
        <GridBg />
        <div className="relative z-10 grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 items-center">
          {/* Left: Headline */}
          <div className="max-w-xl">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 border border-[#0066CC]/30 rounded-full font-mono text-sm text-[#0066CC] bg-[#0066CC]/8 mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-[#2DA66A] shadow-[0_0_8px_rgba(45,166,106,0.3)]" />
              Verification Engine
            </div>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold leading-[1.1] tracking-tight mb-4">
              Datasheet verification that doesn't make stuff up.
            </h1>
            <p className="text-[#8b95a8] text-base sm:text-lg leading-relaxed mb-6">
              AKILI extracts facts from datasheets and grounds every answer in coordinate-level proof — or refuses to guess.
            </p>
            <div className="flex flex-col sm:flex-row gap-4">
              {authAvailable && (
                <button
                  type="button"
                  onClick={signInWithGoogle}
                  className="px-8 py-3.5 bg-[#0066CC] text-white font-semibold rounded-md hover:shadow-[0_0_24px_rgba(0,102,204,0.35)] transition-all hover:-translate-y-0.5 text-center text-lg"
                >
                  Try it with your datasheet
                </button>
              )}
            </div>
          </div>

          {/* Right: Benchmark Table (above the fold) */}
          <div className="lg:pl-4">
            <BenchmarkTable data={DEFAULT_BENCHMARK_DATA} />
          </div>
        </div>
      </section>

      {/* ─── Stats ─── */}
      <RevealSection className="px-6 md:px-12 lg:px-20 py-16 relative" ariaLabel="Key statistics">
        <GridBg />
        <div className="relative z-10 max-w-4xl mx-auto">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            {STATS.map((s) => (
              <div key={s.label} className="text-center p-5 border border-white/6 rounded-lg bg-[#161d2e]">
                <div className="text-3xl sm:text-4xl font-bold text-[#0066CC] mb-1">{s.value}</div>
                <div className="text-xs font-mono text-[#8b95a8] uppercase tracking-wider">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </RevealSection>

      {/* ─── Problem ─── */}
      <RevealSection className="min-h-screen flex flex-col justify-center px-6 md:px-12 lg:px-20 relative" ariaLabel="The problem">
        <GridBg />
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
      </RevealSection>

      {/* ─── How It Works ─── */}
      <RevealSection id="how" className="min-h-screen flex flex-col justify-center px-6 md:px-12 lg:px-20 relative" ariaLabel="How it works">
        <GridBg />
        <div className="relative z-10">
          <p className="text-[#0066CC] font-bold text-sm tracking-widest mb-3">02 — HOW IT WORKS</p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mb-3">Three steps to verified truth.</h2>
          <p className="text-[#8b95a8] max-w-xl leading-relaxed mb-8">
            AI extracts the facts. Deterministic rules verify the answers. No model is in the loop at query time.
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
      </RevealSection>

      {/* ─── Canonical Types ─── */}
      <RevealSection id="types" className="py-24 sm:py-32 px-6 md:px-12 lg:px-20 relative" ariaLabel="Canonical types">
        <GridBg />
        <div className="relative z-10">
          <p className="text-[#0066CC] font-bold text-sm tracking-widest mb-3">03 — THE DATA MODEL</p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mb-3">Five canonical types. Zero ambiguity.</h2>
          <p className="text-[#8b95a8] max-w-xl leading-relaxed mb-8">
            Raw document content is parsed into typed, coordinate-grounded objects.
            If a fact can't be cleanly typed, it's rejected at ingestion — not stored as free text.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {CANONICAL_TYPES.map((t) => (
              <div key={t.name} className="p-5 border border-white/6 rounded-lg bg-[#161d2e] group hover:border-[#0066CC]/30 transition-colors">
                <div className="flex items-center gap-3 mb-3">
                  <span className="font-mono text-xs px-2 py-1 bg-[#0066CC]/10 text-[#0066CC] rounded">{t.name}</span>
                </div>
                <p className="text-sm text-[#8b95a8] leading-relaxed mb-3">{t.desc}</p>
                <div className="font-mono text-xs text-[#f0f2f5]/60 bg-white/4 px-3 py-2 rounded">
                  {t.example}
                </div>
              </div>
            ))}
          </div>
        </div>
      </RevealSection>

      {/* ─── Confidence Tiers ─── */}
      <RevealSection className="py-24 sm:py-32 px-6 md:px-12 lg:px-20 relative" ariaLabel="Confidence tiers">
        <GridBg />
        <div className="relative z-10">
          <p className="text-[#0066CC] font-bold text-sm tracking-widest mb-3">04 — CONFIDENCE SYSTEM</p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mb-3">Three tiers. No gray area.</h2>
          <p className="text-[#8b95a8] max-w-xl leading-relaxed mb-8">
            Every answer is scored across extraction agreement, canonical validation, and verification strength.
            The composite score determines the confidence tier.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 lg:gap-6">
            {TIERS.map((t) => (
              <div key={t.tier} className="p-6 border border-white/6 rounded-lg bg-[#161d2e]">
                <div className="flex items-center gap-3 mb-3">
                  <span
                    className="material-symbols-outlined text-[20px]"
                    style={{ color: t.color }}
                  >
                    {t.icon}
                  </span>
                  <span className="font-bold text-sm tracking-wide" style={{ color: t.color }}>
                    {t.tier}
                  </span>
                  <span className="ml-auto font-mono text-xs text-[#8b95a8]">{t.threshold}</span>
                </div>
                <p className="text-sm text-[#8b95a8] leading-relaxed">{t.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </RevealSection>

      {/* ─── Mock Query Demo ─── */}
      <RevealSection id="demo" className="py-24 sm:py-32 px-6 md:px-12 lg:px-20 relative" ariaLabel="Query demo">
        <GridBg />
        <div className="relative z-10 max-w-3xl mx-auto">
          <p className="text-[#0066CC] font-bold text-sm tracking-widest mb-3">05 — SEE IT IN ACTION</p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mb-3">Ask a question. Get proof.</h2>
          <p className="text-[#8b95a8] max-w-xl leading-relaxed mb-8">
            Here's what a verified query looks like inside Akili.
          </p>

          {/* Mock chat interface */}
          <div className="border border-white/6 rounded-lg bg-[#161d2e] overflow-hidden">
            {/* Question */}
            <div className="p-4 border-b border-white/6">
              <div className="flex justify-end">
                <div className="bg-[#0066CC] text-white px-4 py-2.5 rounded-lg text-sm max-w-xs">
                  {MOCK_QUESTION}
                </div>
              </div>
            </div>
            {/* Answer */}
            <div className="p-4">
              <div className="flex justify-start">
                <div className="bg-white/5 rounded-lg overflow-hidden max-w-md w-full">
                  {/* Verified badge header */}
                  <div className="px-4 py-2.5 border-b border-white/6 bg-[#2DA66A]/10 flex items-center gap-2">
                    <span className="material-symbols-outlined text-[14px] text-[#2DA66A]">verified</span>
                    <span className="text-[#2DA66A] font-bold text-xs tracking-wide uppercase">VERIFIED</span>
                    <span className="ml-auto font-mono text-xs text-[#8b95a8]">{MOCK_RESPONSE.confidence}</span>
                  </div>
                  <div className="px-4 py-3 space-y-2.5">
                    <p className="text-sm font-semibold">{MOCK_RESPONSE.answer}</p>
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2 text-xs text-[#8b95a8]">
                        <span className="material-symbols-outlined text-[12px] text-[#0066CC]">database</span>
                        <span className="font-mono">Source: {MOCK_RESPONSE.source}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-[#8b95a8]">
                        <span className="material-symbols-outlined text-[12px] text-[#0066CC]">rule</span>
                        <span className="font-mono">Rule: {MOCK_RESPONSE.rule}</span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-[#8b95a8]">
                        <span className="material-symbols-outlined text-[12px] text-[#0066CC]">pin_drop</span>
                        <span className="font-mono">Proof: {MOCK_RESPONSE.coords}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </RevealSection>

      {/* ─── Derived Queries ─── */}
      <RevealSection className="py-24 sm:py-32 px-6 md:px-12 lg:px-20 relative" ariaLabel="Derived queries">
        <GridBg />
        <div className="relative z-10">
          <p className="text-[#0066CC] font-bold text-sm tracking-widest mb-3">06 — DERIVED QUERIES</p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mb-3">Compute what the datasheet doesn't say.</h2>
          <p className="text-[#8b95a8] max-w-xl leading-relaxed mb-8">
            Akili doesn't just look up facts — it derives new ones by combining canonical objects with physics-based formulas.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 lg:gap-6">
            {DERIVED_QUERIES.map((q) => (
              <div key={q.name} className="p-5 border border-white/6 rounded-lg bg-[#161d2e] group hover:border-[#0066CC]/30 transition-colors">
                <div className="flex items-center gap-3 mb-2">
                  <h3 className="font-semibold">{q.name}</h3>
                  <span className="font-mono text-xs text-[#0066CC] bg-[#0066CC]/10 px-2 py-0.5 rounded">{q.formula}</span>
                </div>
                <p className="text-sm text-[#8b95a8] leading-relaxed">{q.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </RevealSection>

      {/* ─── Differentiators ─── */}
      <RevealSection className="min-h-screen flex flex-col justify-center px-6 md:px-12 lg:px-20 relative" ariaLabel="Why Akili">
        <GridBg />
        <div className="relative z-10">
          <p className="text-[#0066CC] font-bold text-sm tracking-widest mb-3">07 — WHY AKILI</p>
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
      </RevealSection>

      {/* ─── Industries ─── */}
      <RevealSection className="py-24 sm:py-32 px-6 md:px-12 lg:px-20 relative" ariaLabel="Target industries">
        <GridBg />
        <div className="relative z-10 max-w-3xl mx-auto text-center">
          <p className="text-[#0066CC] font-bold text-sm tracking-widest mb-3">08 — BUILT FOR</p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mb-3">
            Engineering teams who can't afford to guess.
          </h2>
          <p className="text-[#8b95a8] max-w-xl mx-auto leading-relaxed mb-8">
            Any domain where a datasheet error means a field failure, a recall, or worse.
          </p>
          <div className="flex flex-wrap justify-center gap-3">
            {INDUSTRIES.map((ind) => (
              <span key={ind} className="px-5 py-2.5 border border-white/8 rounded-lg text-sm text-[#8b95a8] hover:border-[#0066CC]/30 hover:text-white transition-colors">
                {ind}
              </span>
            ))}
          </div>
        </div>
      </RevealSection>

      {/* ─── CTA ─── */}
      <RevealSection className="min-h-screen flex flex-col justify-center items-center text-center px-6 md:px-12 lg:px-20 relative" ariaLabel="Get started">
        <GridBg />
        <div className="relative z-10 flex flex-col items-center">
          <p className="text-[#0066CC] font-bold text-sm tracking-widest mb-3">09 — GET STARTED</p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight mb-3 max-w-xl">
            Where AI shows its work.
          </h2>
          <p className="text-[#8b95a8] max-w-xl leading-relaxed mb-8">
            Upload your first datasheet and see coordinate-grounded verification in action. Free tier includes 5 documents and 50 queries.
          </p>
          {authAvailable && (
            <button
              type="button"
              onClick={signInWithGoogle}
              className="px-8 py-3 bg-[#0066CC] text-white font-semibold rounded-md hover:shadow-[0_0_24px_rgba(0,102,204,0.35)] transition-all hover:-translate-y-0.5 mb-8"
            >
              Get Started — Free
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
      </RevealSection>
    </div>
  );
};

export default LandingPage;
