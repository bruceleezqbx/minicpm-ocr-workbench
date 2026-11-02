/**
 * 本机改造：本文件在上游 OpenBMB/MiniCPM-OCR 版本基础上被修改。
 * Apache-2.0 §4(b) 要求被修改的文件声明改动；完整改动清单见 E:\OCR\CHANGES.md
 */
import { useMemo } from 'react';

import type { useImageParse } from './useImageParse';
import { useImageParseDraft } from './useImageParseDraft';
import { useImageParseDownload } from './useImageParseDownload';
import { useImageParseRegeneration } from './useImageParseRegeneration';
import { imageParseBlockRanges } from '../utils/imageParseBlocks';
import { imageParseQuality } from '../utils/imageParseQuality';
import {
  imageParseSealDisplayCrops,
  imageParseSealDisplayResult,
} from '../utils/imageParseSealDisplay';

/**
 * Connect the result draft, original-image positioning ranges, and download data, so export uses the current edited content.
 * @param parse current recognition result
 * @param examplePageKey per-page identity of a shared example
 * @returns the draft, positioning ranges, quality summary, and download actions
 */
export function useImageParseResultState(
  parse: ReturnType<typeof useImageParse>,
  examplePageKey?: string,
) {
  const baseRanges = useMemo(
    () => imageParseBlockRanges(parse.markdown, parse.layout),
    [parse.markdown, parse.layout],
  );
  const draft = useImageParseDraft(parse.markdown, examplePageKey ?? parse.resultKey, baseRanges);
  const ranges = draft.ranges;
  const linkedRanges = useMemo(() => [...ranges].map(([id, range]) => ({ id, range })), [ranges]);
  const preview = useMemo(
    () =>
      imageParseSealDisplayResult(
        { markdown: draft.value, blocks: parse.layout },
        parse.recognizeSeal,
        parse.recognizeChart,
        ranges,
      ),
    [draft.value, parse.layout, parse.recognizeChart, parse.recognizeSeal, ranges],
  );
  const previewRanges = useMemo(
    () => imageParseBlockRanges(preview.markdown, preview.blocks),
    [preview.markdown, preview.blocks],
  );
  const previewLinkedRanges = useMemo(
    () => [...previewRanges].map(([id, range]) => ({ id, range })),
    [previewRanges],
  );
  const previewCrops = useMemo(
    () =>
      imageParseSealDisplayCrops(
        parse.layout,
        parse.crops ?? [],
        parse.recognizeSeal,
        parse.recognizeChart,
      ),
    [parse.crops, parse.layout, parse.recognizeChart, parse.recognizeSeal],
  );
  const quality = useMemo(() => imageParseQuality(parse.layout), [parse.layout]);
  // 本机改造：把单块重识别挂上。低分块（置信度来自 Jev 一致性分数）可以在复核面板里
  // 重新识别，重新识别后由本机后端再用 Jev 打一次分，分数口径与页面上的一致。
  const regeneration = useImageParseRegeneration({
    resultKey: parse.resultKey,
    model: 'minicpm-ocr',
    secret: 'local',
    blocks: parse.layout,
    draft,
    documentDataUrl: parse.attachment?.dataUrl ?? '',
    mime: parse.attachment?.mime ?? '',
    pageIndex: parse.pdf?.page ?? 1,
    loading: parse.loading,
  });
  const download = useImageParseDownload({
    markdown: draft.value,
    blocks: parse.layout,
    rotation: parse.rotation,
    ranges,
    edited: draft.manuallyEdited ?? draft.dirty,
    name: parse.attachment?.name,
    page: parse.pdf?.page,
    disabled: parse.loading,
  });
  return {
    draft,
    ranges,
    linkedRanges,
    preview,
    previewRanges,
    previewLinkedRanges,
    previewCrops,
    quality,
    regeneration,
    download,
  };
}
