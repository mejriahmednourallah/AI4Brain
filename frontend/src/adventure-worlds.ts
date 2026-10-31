export type AdventureWorld = {
  id: string;
  dimension: string;
  name: string;
  place: string;
  description: string;
  image: string;
};

export const adventureWorlds: readonly AdventureWorld[] = [
  { id: 'EX-01', dimension: 'working_memory', name: 'Memory', place: 'Lantern Grove', description: 'Notice and remember what matters.', image: '/art/adventure/world-memory.webp' },
  { id: 'EX-02', dimension: 'reasoning', name: 'Reasoning', place: 'Pattern Atelier', description: "Find what's the same, what's different.", image: '/art/adventure/world-reasoning.webp' },
  { id: 'EX-03', dimension: 'attention_inhibition', name: 'Attention', place: 'Signal Observatory', description: "Tune in to what's important.", image: '/art/adventure/world-attention.webp' },
  { id: 'EX-04', dimension: 'flexibility', name: 'Flexibility', place: 'Shifting Gallery', description: 'See it another way.', image: '/art/adventure/world-flexibility.webp' },
  { id: 'EX-05', dimension: 'planning', name: 'Planning', place: "Wayfinder's Garden", description: 'Turn ideas into action.', image: '/art/adventure/world-planning.webp' },
];
