/**
 * 本机改造：本文件在上游 OpenBMB/MiniCPM-OCR 版本基础上被修改。
 * Apache-2.0 §4(b) 要求被修改的文件声明改动；完整改动清单见 E:\OCR\CHANGES.md
 */
import { type ImageParseSource } from '@/api/map/imageParseSource';
import { IMAGE_PARSE_LOCAL_BACKEND } from '@/api/map/request';
import type { ImageParseLayoutBlock } from './imageParseSample';

interface BlockGenerationInput {
  source?: ImageParseSource;
  /** Document-parsing model ID visible to the current logged-in user. */
  model: string;
  /** Plaintext secret of the currently selected API Key; passed in memory only and not persisted to disk. */
  secret: string;
  documentDataUrl: string;
  mime: string;
  pageIndex: number;
}

/**
 * Local single-block recompute: the backend crops the block from the page image,
 * re-recognizes it with MiniCPM-OCR 1.0 and re-scores it with Jev, so the number
 * that comes back is on the same scale as the one already on screen.
 */
async function regenerateLocalBlock(
  input: BlockGenerationInput,
  original: ImageParseLayoutBlock,
  signal: AbortSignal,
): Promise<{ markdown: string; text: string; confidence: number }> {
  const response = await fetch('/api/jev/regenerate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image: input.documentDataUrl,
      // 归一化坐标；后端按页面实际像素换算
      bbox: [original.x, original.y, original.w, original.h],
      label: original.label ?? original.kind,
    }),
    signal,
  });
  const payload = (await response.json().catch(() => ({}))) as {
    error?: string;
    markdown?: string;
    text?: string;
    prob_1?: number | null;
  };
  if (!response.ok) {
    throw new Error(payload.error || 'imageParseRegenerateFailed');
  }
  const markdown = payload.markdown ?? payload.text ?? '';
  const confidence = payload.prob_1 ?? original.confidence ?? 0;
  return { markdown, text: markdown, confidence };
}

/**
 * Real v4 uses only a whole-page reference issued by the server; without proof of origin it must be explicitly unavailable.
 *
 * 本机改造：本地后端自己就是唯一的服务端，不存在"页面凭证"这一层，
 * 所以本机走本地重识别通道；只有非本机部署才要求 source + secret。
 */
export function imageParseBlockGenerator(
  input: BlockGenerationInput,
  original: ImageParseLayoutBlock,
  blockId: string,
  signal: AbortSignal,
) {
  return async (attempt: number, currentBest: ImageParseLayoutBlock) => {
    const requestSignal = AbortSignal.any([signal, AbortSignal.timeout(300_000)]);
    if (IMAGE_PARSE_LOCAL_BACKEND) {
      return regenerateLocalBlock(input, original, requestSignal);
    }
    if (!input.source) throw new Error('imageParseRegenerateSourceMissing');
    if (input.pageIndex !== input.source.pageIndex)
      throw new Error('imageParseRegenerateSourceInvalid');
    const { regenerateImageParseV4 } = await import('@/api/map/imageParseV2');
    return regenerateImageParseV4(input.source, original, requestSignal, input.model, input.secret);
  };
}
