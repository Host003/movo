import type { ArtifactItem } from './delivery'

/** Show deliverables only after the turn settles, preferring those named in its answer. */
export function visibleAnswerArtifacts(
  artifacts: ArtifactItem[],
  runStatus: string,
  answer: string,
): ArtifactItem[] {
  if (runStatus === 'running') return []
  const text = String(answer || '')
  const byPath = artifacts.filter((item) => item.object_path && text.includes(item.object_path))
  if (byPath.length) return byPath
  const byFilename = artifacts.filter((item) => item.filename && text.includes(item.filename))
  return byFilename.length ? byFilename : artifacts
}
