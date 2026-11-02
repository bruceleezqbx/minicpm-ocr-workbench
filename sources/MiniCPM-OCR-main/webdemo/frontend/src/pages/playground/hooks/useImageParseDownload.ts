/**
 * 本机改造：本文件在上游 OpenBMB/MiniCPM-OCR 版本基础上被修改。
 * Apache-2.0 §4(b) 要求被修改的文件声明改动；完整改动清单见 E:\OCR\CHANGES.md
 */
import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useToast } from '@map/ui';

import {
  createImageParseExport,
  imageParseExportFileName,
  saveImageParseExport,
  type ImageParseDownloadFormat,
  type ImageParseExportInput,
} from '../utils/imageParseExport';

interface ImageParseDownloadInput extends ImageParseExportInput {
  page?: number;
  disabled: boolean;
}

/**
 * Download of the current OCR result: keep the snapshot from the click, forbid concurrent generation, and restore the entry on failure.
 * @param input draft, layout info, file name, and workspace disabled state
 * @returns download state and the format-selection callback
 */
export function useImageParseDownload(input: ImageParseDownloadInput) {
  const { t } = useTranslation('playground');
  const { toast } = useToast();
  const [downloading, setDownloading] = useState(false);
  const pending = useRef(false);

  async function download(format: ImageParseDownloadFormat) {
    if (input.disabled || pending.current || !input.markdown.trim()) return;
    pending.current = true;
    setDownloading(true);
    try {
      const blob = await createImageParseExport(format, input);
      const saved = await saveImageParseExport(
        blob,
        imageParseExportFileName(input.name, format, input.page),
      );
      // 桌面壳里文件是 Python 直接写到磁盘的，给用户看落盘位置；
      // 浏览器走系统下载，浏览器自己会提示，这里不再打扰。
      if (saved?.path) {
        toast({ title: t('imageParseDownloadSaved', { path: saved.path }) });
      }
    } catch {
      toast({ title: t('imageParseDownloadFailed'), variant: 'error' });
    } finally {
      pending.current = false;
      setDownloading(false);
    }
  }

  return { downloading, download };
}
