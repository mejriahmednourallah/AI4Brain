/** Maximum spoken reply length; the written answer is never shortened. */
export const MAX_SPEECH_SENTENCE_LENGTH = 120;

/** A safe fallback that points to the full written reply without adding advice. */
export const WRITTEN_REPLY_PROMPT = 'Please read the written reply for details.';

/**
 * Return only the first complete sentence when it fits the short voice budget.
 * Never cut off a sentence or concatenate the rest of a long answer.
 */
export function speechExcerpt(value: string, limit = MAX_SPEECH_SENTENCE_LENGTH): string {
  const text = value.trim().replace(/\s+/g, ' ');
  if (!text || !Number.isInteger(limit) || limit < 1) return WRITTEN_REPLY_PROMPT;

  const boundary = /[.!?][”’"')\]]*(?=\s|$)/.exec(text);
  if (!boundary) return WRITTEN_REPLY_PROMPT;

  const sentence = text.slice(0, boundary.index + boundary[0].length).trim();
  return sentence.length <= limit ? sentence : WRITTEN_REPLY_PROMPT;
}
