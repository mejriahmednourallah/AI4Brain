import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { Check } from 'lucide-react';
import { motion } from 'motion/react';
import type { HomeWorldProgress } from './home-model';
import type { AdventureWorld } from './adventure-worlds';

export type World = AdventureWorld;

export function Button({ variant = 'secondary', type = 'button', className = '', children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'text'; children: ReactNode }) {
  return <button {...props} type={type} className={`home-button home-button-${variant}${className ? ` ${className}` : ''}`}>{children}</button>;
}

export function SceneLayer({ className = '', src, alt }: { className?: string; src: string; alt: string }) {
  return <div className={`home-scene-layer ${className}`} aria-hidden={alt ? undefined : true}>
    <img src={src} alt={alt} />
  </div>;
}

function progressLabel(progress: HomeWorldProgress): string {
  if (progress === 'assessed') return 'Baseline complete';
  if (progress === 'in_progress') return 'In progress';
  if (progress === 'not_assessed') return 'Not assessed';
  return 'Status unavailable';
}

function WorldIsland({ world, index, progress, loading, onChoose }: { world: World; index: number; progress: HomeWorldProgress; loading: boolean; onChoose: (id: string) => void }) {
  const status = progressLabel(progress);
  const description = `${world.name}, ${world.place}. ${world.description} ${status}.`;
  return <motion.button type="button" className={`home-island home-island-${index + 1}`} onClick={() => onChoose(world.id)} disabled={loading} aria-label={description}
    whileHover={{ y: -5 }} whileTap={{ scale: .985 }} transition={{ type: 'spring', stiffness: 300, damping: 22 }}>
    <span className="home-island-art"><img src={world.image} alt="" loading="lazy" /></span>
    <strong>{world.name}</strong>
    <span className="home-island-place">{world.place}</span>
    <span className="home-island-description">{world.description}</span>
    <span className={`home-island-status${progress === 'assessed' ? ' is-complete' : ''}`}>{progress === 'assessed' ? <Check size={12} /> : <span className="home-status-dot" />}{status}</span>
  </motion.button>;
}

export function WorldJourney({ worlds, progress, loading, onChoose }: { worlds: readonly World[]; progress: Readonly<Record<string, HomeWorldProgress>>; loading: boolean; onChoose: (id: string) => void }) {
  return <div className="home-journey" aria-label="Five connected learning worlds">
    <svg className="home-journey-path" viewBox="0 0 1000 180" preserveAspectRatio="none" aria-hidden="true">
      <path d="M100 104 C170 104 190 130 250 130 S380 67 440 85 S550 125 625 125 S740 76 795 95 S890 115 950 105" />
      {[100, 285, 490, 690, 900].map((x, i) => <circle key={i} cx={x} cy={[104, 117, 95, 113, 107][i]} r="5" />)}
    </svg>
    {worlds.map((world, index) => <WorldIsland key={world.id} world={world} index={index} progress={progress[world.dimension] ?? 'unavailable'} loading={loading} onChoose={onChoose} />)}
  </div>;
}
