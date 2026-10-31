import { ArrowRight, BarChart3, BookOpen, CalendarDays, ChevronRight, CircleHelp, Play } from 'lucide-react';
import { Button, SceneLayer, WorldJourney } from './home-primitives';
import { adventureWorlds } from './adventure-worlds';
import { toHomePresentation, type HomeDashboardSource } from './home-model';
import './home.css';

export default function AdventureHome({ dashboard, loading, error, notice = null, sessionId, consent, setConsent, onPlay, onWorld, onRetry, onPlan }: {
  dashboard: HomeDashboardSource | null; loading: boolean; error: string | null; notice?: string | null; sessionId: string | null; consent: boolean; setConsent: (value: boolean) => void;
  onPlay: () => void; onWorld: (exerciseId: string) => void; onRetry: () => void; onPlan: () => void;
}) {
  const presentation = toHomePresentation(dashboard, loading, Boolean(error));
  const hasSession = Boolean(sessionId);
  const { coverage, plan, participation } = presentation;
  const coverageCopy = coverage.state === 'available'
    ? `${coverage.assessedCount} of ${coverage.totalCount} baseline families complete`
    : coverage.state === 'loading' ? 'Loading saved observations…' : 'Saved observations unavailable';

  return <main className="home-v3">
    <section className="home-hero" aria-labelledby="home-title">
      <SceneLayer className="home-hero-scene" src="/art/adventure/home-hero-plate.png" alt="" />
      <div className="home-hero-copy">
        <p className="home-eyebrow">Real practice. Real change.</p>
        <h1 id="home-title">A little practice.<br />A new possibility.</h1>
        <p className="home-subtitle">Five worlds. One practice journey.</p>
        {error && <div className="home-alert" role="alert"><span>{error}</span><button type="button" onClick={onRetry}>Retry</button></div>}
        {!error && notice && <p className="home-notice" role="status">{notice}</p>}
        <div className="home-action-group">
          <Button variant="primary" className="home-start" onClick={onPlay} disabled={loading || (!hasSession && !consent)}>
            <Play size={20} fill="currentColor" aria-hidden="true" />
            <span>{loading ? 'Opening your journey…' : hasSession ? 'Continue your journey' : 'Begin your journey'}</span>
            <ArrowRight size={20} aria-hidden="true" />
          </Button>
          {!hasSession && <label className="home-consent">
            <input type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} />
            <span>Preliminary task observations, not a clinical assessment.</span>
            <span className="home-info" title="This local experience is not a clinical assessment." aria-label="This local experience is not a clinical assessment."><CircleHelp size={16} /></span>
          </label>}
          {hasSession && <span className="home-local-note">Your session is saved on this device.</span>}
        </div>
      </div>
    </section>

    <aside className="home-summary" aria-label="Plan and participation">
      <section className="home-summary-section" aria-labelledby="home-plan-title">
        <h2 id="home-plan-title">Your plan</h2>
        {plan.state === 'available' ? <>
          <p className="home-plan-kicker">Next in your plan</p>
          <ol className="home-plan-steps">{plan.steps.slice(0, 2).map((step, index) => {
            const world = adventureWorlds.find(item => item.dimension === step.dimension || item.id === step.exerciseId);
            return <li key={step.id}><span className="home-step-index">{index + 1}</span><span><strong>{world?.name ?? step.title}</strong>{step.rationale && <small>{step.rationale}</small>}</span></li>;
          })}</ol>
        </> : <>
          <div className="home-summary-icon"><CalendarDays size={28} /></div>
          <p className="home-summary-lead">{plan.state === 'loading' ? 'Loading your plan…' : plan.state === 'unavailable' ? 'Plan unavailable.' : 'Choose a world to begin.'}</p>
          <p className="home-summary-copy">{plan.state === 'empty' ? 'Explore the five worlds below and start with the one that interests you most.' : plan.state === 'loading' ? 'Your saved plan will appear here.' : 'Try again when your saved plan is available.'}</p>
        </>}
        <Button variant="text" className="home-plan-link" onClick={onPlan}>View your plan <ChevronRight size={17} /></Button>
      </section>
      <section className="home-summary-section home-participation" aria-labelledby="home-participation-title">
        <h2 id="home-participation-title">Your participation</h2>
        {participation.state !== 'available' && <div className="home-summary-icon"><BarChart3 size={27} /></div>}
        <p className="home-summary-lead">{participation.state === 'loading' ? 'Loading participation…' : participation.state === 'unavailable' ? 'Participation unavailable.' : participation.state === 'empty' ? 'No practice recorded yet.' : `${(participation.practiceCount ?? 0) + (participation.trainingCount ?? 0)} practice activities recorded.`}</p>
        <p className="home-summary-copy">{participation.state === 'available'
          ? `${participation.xp === null ? 'Participation points unavailable.' : `${participation.xp.toLocaleString()} participation XP`} · not a cognitive measure`
          : participation.state === 'empty' ? 'Your activity will appear here after you begin.'
            : participation.state === 'loading' ? 'Your saved activity will appear here.' : 'Saved participation could not be loaded.'}</p>
        {participation.state === 'available' && participation.milestoneCount !== null && participation.milestoneCount > 0 && <p className="home-summary-copy">{participation.completedMilestones ?? 0} of {participation.milestoneCount} evidence milestones complete</p>}
      </section>
    </aside>

    <section className="home-worlds" aria-labelledby="worlds-title">
      <div className="home-worlds-heading">
        <p className="home-eyebrow">Five worlds. One journey.</p>
        <h2 id="worlds-title">Explore the worlds</h2>
        <p>Each world trains a different way your mind works.</p>
          <span className="home-coverage" aria-live="polite">{coverageCopy}{coverage.state === 'available' && ' · practice stays separate'}</span>
      </div>
      <WorldJourney worlds={adventureWorlds} progress={presentation.worlds} loading={loading} onChoose={onWorld} />
    </section>
    <span className="home-watermark" aria-hidden="true"><BookOpen size={13} /> Local · non-clinical</span>
  </main>;
}
