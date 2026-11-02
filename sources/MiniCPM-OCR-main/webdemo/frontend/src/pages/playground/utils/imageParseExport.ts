/**
 * 本机改造：本文件在上游 OpenBMB/MiniCPM-OCR 版本基础上被修改。
 * Apache-2.0 §4(b) 要求被修改的文件声明改动；完整改动清单见 E:\OCR\CHANGES.md
 */
import type { ImageParseTextRange } from './imageParseBlocks';
import { imageParseBlockId } from './imageParseBlocks';
import type { ImageParseLayoutBlock } from './imageParseSample';
import type { ImageParseRotationInfo } from './imageParseSample';

/** Download formats supported for the current OCR result. */
export type ImageParseDownloadFormat = 'markdown' | 'json' | 'word' | 'word-math';

/** A download snapshot does not accept a source token, API Key, or the raw request, so credentials do not enter the exported file. */
export interface ImageParseExportInput {
  markdown: string;
  blocks: readonly ImageParseLayoutBlock[];
  /** Original document name; used for the download file name and the Word export header. */
  name?: string;
  rotation?: ImageParseRotationInfo;
  ranges?: ReadonlyMap<string, ImageParseTextRange>;
  edited?: boolean;
}

const EXTENSIONS: Record<ImageParseDownloadFormat, string> = {
  markdown: 'md',
  json: 'json',
  word: 'docx',
  'word-math': 'docx',
};

/**
 * Name the current result from the original document; a PDF is explicitly marked with the current page so it is not mistaken for an export of every page.
 * @param name original file name
 * @param format download format
 * @param page optional PDF page number, starting at 1
 * @returns download file name with the correct extension
 */
export function imageParseExportFileName(
  name: string | undefined,
  format: ImageParseDownloadFormat,
  page?: number,
): string {
  const base = name?.replace(/\.[^.]+$/, '').trim() || 'image-parse';
  return `${base}${page ? `-page-${page}` : ''}.${EXTENSIONS[format]}`;
}

/**
 * Create download content; Word is loaded on demand, and JSON rebuilds only the layout fields that are allowed to be exported.
 * @param format format the user selected
 * @param input current editable body and recognition-block snapshot
 * @returns a file Blob, without modifying the draft or the service return value
 */
export async function createImageParseExport(
  format: ImageParseDownloadFormat,
  input: ImageParseExportInput,
): Promise<Blob> {
  if (format === 'word') {
    const { createImageParseWordBlob } = await import('./imageParseWord');
    return createImageParseWordBlob(input.markdown);
  }
  if (format === 'word-math') {
    // 本机扩展：服务端用 Pandoc 导出，公式成为 Word 原生公式（OMML）。
    // 前端自带的 Word 导出把公式保留成 LaTeX 源码纯文本，两者定位不同。
    const response = await fetch('/api/export/word', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ markdown: input.markdown, name: input.name }),
    });
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as { error?: string };
      throw new Error(payload.error || 'imageParseDownloadFailed');
    }
    return response.blob();
  }
  if (format === 'markdown')
    return new Blob([input.markdown], { type: 'text/markdown;charset=utf-8' });

  const blocks = input.blocks.map((block, index) => {
    const range = input.ranges?.get(imageParseBlockId(block, index));
    return {
      id: block.id,
      order: block.order,
      label: block.label,
      status: block.status,
      kind: block.kind,
      x: block.x,
      y: block.y,
      w: block.w,
      h: block.h,
      regions: block.regions,
      ttsInvalid: block.ttsInvalid,
      // text and confidence are the original recognition evidence; only positionable Markdown is updated with a manual edit.
      text: block.text,
      markdown: range ? input.markdown.slice(range.start, range.end) : block.markdown,
      confidence: block.confidence,
      markdownStart: range?.start,
      markdownEnd: range?.end,
    };
  });
  const json = JSON.stringify(
    {
      markdown: input.markdown,
      blocks,
      rotation: input.rotation,
      edited: Boolean(input.edited),
    },
    null,
    2,
  );
  return new Blob([json], { type: 'application/json;charset=utf-8' });
}

/**
 * Start a local download and release the object URL after a delay, leaving the browser time to consume the file.
 * @param blob file content
 * @param fileName download file name
 */
export function saveImageParseExport(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.append(link);
  try {
    link.click();
  } finally {
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}
