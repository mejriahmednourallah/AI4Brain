export type HomeDataState = 'loading' | 'unavailable' | 'empty' | 'available';
export type HomeWorldProgress = 'unavailable' | 'not_assessed' | 'in_progress' | 'assessed';

export type HomePlanStep = { id: string; title: string; rationale: string | null; dimension: string | null; exerciseId: string | null };
export type HomePresentation = {
  coverage: { state: 'loading' | 'unavailable' | 'available'; assessedCount: number | null; totalCount: number | null };
  plan: { state: HomeDataState; steps: HomePlanStep[] };
  participation: { state: HomeDataState; practiceCount: number | null; trainingCount: number | null; xp: number | null; milestoneCount: number | null; completedMilestones: number | null };
  worlds: Record<string, HomeWorldProgress>;
};

type PlanStepSource = { id?: unknown; step_id?: unknown; title?: unknown; rationale?: unknown; dimension?: unknown; dimension_id?: unknown; exercise_id?: unknown; exercise_type_id?: unknown };
export type HomeDashboardSource = {
  task_coverage?: { assessed_count?: number | null; total_count?: number | null; dimensions?: { dimension: string; status?: string | null; evidence_count?: number | null }[] | null } | null;
  plan?: { latest?: { steps?: PlanStepSource[] | null; plan?: { steps?: PlanStepSource[] | null } | null } | null } | null;
  participation?: { practice_trial_count?: number | null; training_trial_count?: number | null; xp?: number | null } | null;
  milestones?: { achieved: boolean }[] | null;
};

const finite = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) ? value : null;
const asText = (value: unknown): string | null => typeof value === 'string' && value.trim() ? value.trim() : null;

function adaptSteps(source: PlanStepSource[]): HomePlanStep[] {
  return source.map((step, index) => ({
    id: asText(step.id) ?? asText(step.step_id) ?? `step-${index + 1}`,
    title: asText(step.title) ?? 'Planned activity',
    rationale: asText(step.rationale),
    dimension: asText(step.dimension) ?? asText(step.dimension_id),
    exerciseId: asText(step.exercise_id) ?? asText(step.exercise_type_id),
  }));
}

export function toHomePresentation(dashboard: HomeDashboardSource | null, loading: boolean, hasError: boolean): HomePresentation {
  const coverage = dashboard?.task_coverage;
  const assessedCount = finite(coverage?.assessed_count);
  const totalCount = finite(coverage?.total_count);
  const coverageState = coverage && assessedCount !== null && totalCount !== null
    ? 'available' as const
    : loading && !hasError ? 'loading' as const : 'unavailable' as const;

  const latestPlan = dashboard?.plan?.latest;
  const sourceSteps = latestPlan?.steps ?? latestPlan?.plan?.steps;
  const planSteps = sourceSteps ? adaptSteps(sourceSteps) : [];
  const planState: HomeDataState = !dashboard?.plan
    ? loading && !hasError ? 'loading' : 'unavailable'
    : planSteps.length ? 'available' : 'empty';

  const participationSource = dashboard?.participation;
  const practiceCount = finite(participationSource?.practice_trial_count);
  const trainingCount = finite(participationSource?.training_trial_count);
  const xp = finite(participationSource?.xp);
  const participationState: HomeDataState = !participationSource || practiceCount === null || trainingCount === null
    ? loading && !hasError ? 'loading' : 'unavailable'
    : practiceCount + trainingCount > 0 ? 'available' : 'empty';
  const milestones = dashboard?.milestones;
  const completedMilestones = milestones ? milestones.filter(item => item.achieved).length : null;
  const worlds: Record<string, HomeWorldProgress> = {};
  for (const row of coverage?.dimensions ?? []) {
    if (row.status === 'ASSESSED') worlds[row.dimension] = 'assessed';
    else if (row.status === 'IN_PROGRESS' || (finite(row.evidence_count) ?? 0) > 0) worlds[row.dimension] = 'in_progress';
    else if (row.status === 'NOT_ASSESSED' || row.status === 'UNASSESSED' || finite(row.evidence_count) === 0) worlds[row.dimension] = 'not_assessed';
    else worlds[row.dimension] = 'unavailable';
  }

  return {
    coverage: { state: coverageState, assessedCount, totalCount },
    plan: { state: planState, steps: planSteps },
    participation: { state: participationState, practiceCount, trainingCount, xp, milestoneCount: milestones?.length ?? null, completedMilestones },
    worlds,
  };
}
