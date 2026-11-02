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
 * pywebview 注入的 JS 桥，只有桌面壳里才有（浏览器里 window.pywebview 是 undefined）。
 *
 * 桌面壳用 Edge WebView2，而 pywebview 没有接 CoreWebView2.DownloadStarting，
 * 所以 WebView2 会静默掐掉浏览器的下载机制：blob 链接不落盘，
 * 带 Content-Disposition 的跳转也不落盘，点下载毫无反应。
 * 因此桌面壳里改走这条 JS->Python 桥，由 Python 直接把文件写到磁盘。
 */
interface DesktopBridge {
  api?: {
    save_bytes?: (
      filename: string,
      contentBase64: string,
    ) => Promise<{ ok: boolean; path?: string; bytes?: number; error?: string }>;
  };
}

/**
 * 桌面壳里落盘后的结果。
 */
export interface ImageParseExportSaveResult {
  /** 桌面壳写盘后的绝对路径；浏览器下载时为空。 */
  path?: string;
}

/**
 * 是否运行在桌面壳里。
 *
 * 桌面壳打开工作台时会带 ?shell=desktop（见 scripts/desktop_app.py），
 * 这样在模块加载时就能同步判定，浏览器里不会为等桌面桥白等几秒。
 */
const DESKTOP_SHELL =
  typeof window !== 'undefined' &&
  new URLSearchParams(window.location.search).get('shell') === 'desktop';

function desktopBridge(): DesktopBridge['api'] | undefined {
  if (typeof window === 'undefined') return undefined;
  return (window as Window & { pywebview?: DesktopBridge }).pywebview?.api;
}

/**
 * 拿桌面桥。桌面壳里 pywebview 注入 JS 桥可能比页面渲染晚一点，轮询等它就绪。
 * @param timeoutMs 最长等待时间
 * @returns 桌面桥的 api；不在桌面壳里、或等不到就返回 undefined
 */
async function waitForDesktopBridge(timeoutMs = 8000): Promise<DesktopBridge['api'] | undefined> {
  if (!DESKTOP_SHELL) return undefined;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const api = desktopBridge();
    if (api?.save_bytes) return api;
    await new Promise((resolve) => {
      window.setTimeout(resolve, 100);
    });
  }
  return undefined;
}

/**
 * Blob 转 base64。分块拼，避免大文件一次性展开导致调用栈溢出。
 * @param blob 文件内容
 * @returns base64 字符串
 */
async function blobToBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  const chunk = 0x8000;
  let binary = '';
  for (let i = 0; i < bytes.length; i += chunk) {
    const slice = bytes.subarray(i, i + chunk);
    let piece = '';
    for (let j = 0; j < slice.length; j += 1) piece += String.fromCharCode(slice[j]);
    binary += piece;
  }
  return btoa(binary);
}

/**
 * 保存导出结果：桌面壳走 JS 桥由 Python 落盘，浏览器走官方那套 blob 下载。
 * @param blob 文件内容
 * @param fileName 下载文件名
 * @returns 桌面壳落盘时的文件路径
 */
export async function saveImageParseExport(
  blob: Blob,
  fileName: string,
): Promise<ImageParseExportSaveResult> {
  const bridge = await waitForDesktopBridge();
  if (bridge?.save_bytes) {
    const result = await bridge.save_bytes(fileName, await blobToBase64(blob));
    if (!result?.ok) throw new Error(result?.error || 'imageParseDownloadFailed');
    return { path: result.path };
  }
  if (DESKTOP_SHELL) {
    // 在桌面壳里却拿不到 JS 桥：走浏览器下载是不落盘的，直接报错让用户看见。
    throw new Error('imageParseDownloadFailed');
  }

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
  return {};
}
