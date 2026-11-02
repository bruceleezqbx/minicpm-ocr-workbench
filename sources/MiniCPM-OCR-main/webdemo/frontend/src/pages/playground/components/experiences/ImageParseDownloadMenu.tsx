/**
 * 本机改造：本文件在上游 OpenBMB/MiniCPM-OCR 版本基础上被修改。
 * Apache-2.0 §4(b) 要求被修改的文件声明改动；完整改动清单见 E:\OCR\CHANGES.md
 */
import { Download, FileJson, FileText, FileType2, Loader2, Sigma } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import {
  Button,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
  cn,
} from '@map/ui';

import type { ImageParseDownloadFormat } from '../../utils/imageParseExport';
import { useImageParseDownloadMenu } from '../../hooks/useImageParseDownloadMenu';
import { WORKSPACE_CONTROL } from '../../utils/imageParseWorkspaceStyles';

interface ImageParseDownloadMenuProps {
  disabled: boolean;
  downloading: boolean;
  onDownload: (format: ImageParseDownloadFormat) => void;
}

const FORMATS = [
  { format: 'markdown', label: 'Markdown', extension: '.md', icon: FileText },
  { format: 'json', label: 'JSON', extension: '.json', icon: FileJson },
  { format: 'word', label: 'Word', extension: '.docx', icon: FileType2 },
  // 本机扩展：走服务端 Pandoc，公式是 Word 原生公式（OMML，可继续编辑）。
  { format: 'word-math', label: 'Word（公式可编辑）', extension: '.docx', icon: Sigma },
] as const;

/**
 * OCR download-format menu; keep the original icon entry and export the current result by the selection.
 * @param props Disabled state, generation state, and format-selection callback
 * @returns A command menu for Markdown, JSON, and Word
 */
export function ImageParseDownloadMenu({
  disabled,
  downloading,
  onDownload,
}: ImageParseDownloadMenuProps) {
  const { t } = useTranslation('playground');
  const menu = useImageParseDownloadMenu(downloading);
  const { triggerRef } = menu;
  const label = t('imageParseDownload');
  const hint = t(downloading ? 'imageParseDownloading' : 'imageParseDownloadHint');
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip open={menu.tooltipOpen} onOpenChange={menu.onTooltipOpenChange}>
        <DropdownMenu open={menu.open} onOpenChange={menu.onOpenChange}>
          <TooltipTrigger asChild>
            <DropdownMenuTrigger asChild>
              <Button
                ref={triggerRef}
                type="button"
                variant="ghost"
                disabled={disabled}
                data-tour="image-parse-download"
                aria-label={label}
                aria-busy={downloading}
                title={hint}
                className={cn(
                  WORKSPACE_CONTROL,
                  'gap-1.5',
                  'text-muted-foreground hover:text-foreground aria-expanded:bg-accent',
                )}
              >
                {downloading ? (
                  <Loader2
                    className="size-4 animate-spin motion-reduce:animate-none"
                    aria-hidden="true"
                  />
                ) : (
                  <Download className="size-4" aria-hidden="true" />
                )}
                <span className="whitespace-nowrap">{label}</span>
              </Button>
            </DropdownMenuTrigger>
          </TooltipTrigger>
          <DropdownMenuContent
            align="end"
            aria-label={label}
            onCloseAutoFocus={menu.onCloseAutoFocus}
          >
            {FORMATS.map(({ format, label, extension, icon: Icon }) => (
              <DropdownMenuItem
                key={format}
                aria-label={`${label} ${extension}`}
                disabled={disabled}
                onSelect={() => onDownload(format)}
              >
                <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
                <span>{label}</span>
                <span className="ml-auto pl-3 text-xs text-muted-foreground">{extension}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
        {menu.open ? null : <TooltipContent>{hint}</TooltipContent>}
      </Tooltip>
    </TooltipProvider>
  );
}
