import assert from 'node:assert/strict'
import { renderAssistantMarkdown } from '../src/utils/assistantMarkdown'

const path = 'user/2026/10/19/report.pdf'
const markdown = `[下载 PDF](${path})`
const verified = renderAssistantMarkdown(markdown, { artifactPaths: [path] })
assert.match(verified, /data-artifact-path="user\/2026\/10\/19\/report\.pdf"/)
assert.doesNotMatch(verified, /href=/)

const unverified = renderAssistantMarkdown(markdown, { artifactPaths: ['user/other.pdf'] })
assert.doesNotMatch(unverified, /data-artifact-path|href=/)
assert.match(unverified, /\[下载 PDF\]/)
