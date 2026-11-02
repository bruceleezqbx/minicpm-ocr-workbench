/**
 * Document-parsing feature flags.
 *
 * 本机改造：复核入口（低分块标注 / 质量分列表 / 一键重识别）默认是关的，
 * 而它正是本机用 MiniCPM-OCR Jev 一致性分数驱动的那条链路，所以改为可用环境变量开关、默认打开。
 * 设 VITE_IMAGE_PARSE_REVIEW=false 可以关回去。
 */
export const IMAGE_PARSE_REVIEW_ENABLED = import.meta.env.VITE_IMAGE_PARSE_REVIEW !== 'false';

/** Playground table merge is on by default; cross-page tables and adjacent tables in a single image share the build flag. */
export const IMAGE_PARSE_CROSS_PAGE_MERGE_ENABLED =
  import.meta.env.VITE_IMAGE_PARSE_CROSS_PAGE_MERGE !== 'false';
