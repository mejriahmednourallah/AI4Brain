import { useEffect, useRef, useState } from 'react';
import {
  Activity,
  BarChart3,
  ClipboardList,
  Database,
  Gamepad2,
  Home,
  MoreHorizontal,
  Network,
  Play,
  Sparkles,
  type LucideIcon,
} from 'lucide-react';

export type Page =
  | 'welcome'
  | 'assessment'
  | 'overview'
  | 'brain'
  | 'practice'
  | 'plan'
  | 'collaboration'
  | 'hybrid';

type NavigationItem = {
  page: Page;
  label: string;
  icon: LucideIcon;
};

const navItems: NavigationItem[] = [
  { page: 'welcome', label: 'Play', icon: Home },
  { page: 'overview', label: 'Insights', icon: BarChart3 },
  { page: 'assessment', label: 'Assessment', icon: Play },
  { page: 'brain', label: 'Evidence graph', icon: Network },
  { page: 'plan', label: 'Your plan', icon: ClipboardList },
  { page: 'practice', label: 'Practice block', icon: Sparkles },
  { page: 'collaboration', label: 'Collaboration', icon: Activity },
  { page: 'hybrid', label: 'Hybrid lab', icon: Gamepad2 },
];

type HeaderProps = {
  setPage: (page: Page) => void;
  mode: string;
  setMode: (mode: 'analytics' | 'quest') => void;
};

export function Header({ setPage, mode, setMode }: HeaderProps) {
  return (
    <header className="adventure-header">
      <a
        className="adventure-brand"
        href="#play"
        onClick={event => {
          event.preventDefault();
          setPage('welcome');
        }}
      >
        <span className="adventure-brand-mark"><Sparkles size={16} /></span>
        <span>AI4BRAIN<small>LEARNING ADVENTURE</small></span>
      </a>
      <div className="adventure-header-meta">
        <span className="adventure-local-dot" />
        <span>Saved on this device</span>
      </div>
      <div className="view-switch" role="group" aria-label="Insights presentation">
        <button
          className={mode === 'analytics' ? 'selected' : ''}
          aria-pressed={mode === 'analytics'}
          onClick={() => setMode('analytics')}
        >
          Analytics
        </button>
        <button
          className={mode === 'quest' ? 'selected' : ''}
          aria-pressed={mode === 'quest'}
          onClick={() => setMode('quest')}
        >
          Quest
        </button>
      </div>
    </header>
  );
}

type NavigationProps = {
  page: Page;
  onNavigate: (page: Page) => void;
  onData: () => void;
  assessmentLabel?: string;
};

export function DesktopNavigation({ page, onNavigate, onData, assessmentLabel = 'Assessment' }: NavigationProps) {
  return (
    <aside className="adventure-sidebar">
      {page === 'welcome' && (
        <a
          className="home-sidebar-brand"
          href="#play"
          onClick={event => {
            event.preventDefault();
            onNavigate('welcome');
          }}
        >
          AI4BRAIN
        </a>
      )}
      <span className="adventure-sidebar-label">Your space</span>
      <nav className="adventure-desktop-nav" aria-label="Main navigation">
        {navItems.map(({ page: target, label, icon: Icon }) => (
          <button
            key={target}
            className={`adventure-nav-item${page === target ? ' active' : ''}`}
            aria-current={page === target ? 'page' : undefined}
            onClick={() => onNavigate(target)}
          >
            <Icon size={18} />
            <span>{target === 'assessment' ? assessmentLabel : label}</span>
          </button>
        ))}
      </nav>
      <div className="adventure-sidebar-bottom">
        <button onClick={onData}><Database size={17} /> Data &amp; privacy</button>
        <span>Preliminary task observations</span>
      </div>
    </aside>
  );
}

const mobileMainPages: Page[] = ['welcome', 'overview', 'plan', 'brain'];
const mobileLabels: Partial<Record<Page, string>> = {
  welcome: 'Play',
  overview: 'Insights',
  plan: 'Plan',
  brain: 'Brain',
};
const mobileIcons: Partial<Record<Page, LucideIcon>> = {
  welcome: Home,
  overview: BarChart3,
  plan: ClipboardList,
  brain: Network,
};

export function MobileNavigation({ page, onNavigate, onData, assessmentLabel = 'Assessment' }: NavigationProps) {
  const [open, setOpen] = useState(false);
  const moreRef = useRef<HTMLButtonElement>(null);

  const choose = (target: Page) => {
    setOpen(false);
    onNavigate(target);
  };

  useEffect(() => {
    setOpen(false);
  }, [page]);

  useEffect(() => {
    if (!open) return;

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      setOpen(false);
      requestAnimationFrame(() => moreRef.current?.focus());
    };

    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [open]);

  return (
    <>
      <nav className="adventure-mobile-nav" aria-label="Primary navigation">
        {mobileMainPages.map(target => {
          const Icon = mobileIcons[target];
          return (
            <button
              type="button"
              key={target}
              className={page === target ? 'active' : ''}
              aria-current={page === target ? 'page' : undefined}
              onClick={() => choose(target)}
            >
              {Icon && <Icon />}
              <span>{mobileLabels[target]}</span>
            </button>
          );
        })}
        <button
          type="button"
          ref={moreRef}
          data-modal-return
          className={open ? 'active' : ''}
          aria-expanded={open}
          aria-controls="adventure-more-menu"
          onClick={() => setOpen(value => !value)}
        >
          <MoreHorizontal />
          <span>More</span>
        </button>
      </nav>
      {open && (
        <div className="adventure-more-menu" id="adventure-more-menu" role="menu">
          {navItems
            .filter(item => !mobileMainPages.includes(item.page))
            .map(({ page: target, label, icon: Icon }) => (
              <button
                type="button"
                role="menuitem"
                key={target}
                onClick={() => choose(target)}
              >
                <Icon size={18} />
                {target === 'assessment' ? assessmentLabel : label}
              </button>
            ))}
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onData();
            }}
          >
            <Database size={18} />
            Data &amp; privacy
          </button>
        </div>
      )}
    </>
  );
}
