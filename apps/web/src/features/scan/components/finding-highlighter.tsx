"use client";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { categoryLabel, formatConfidence } from "@/lib/format";
import { buildHighlightSegments, type SpanFinding } from "@/lib/highlight";

/** Renders text with each finding span underlined and tinted, with a hover tooltip. */
export function FindingHighlighter({ text, findings }: { text: string; findings: SpanFinding[] }) {
  const segments = buildHighlightSegments(text, findings);
  if (segments.length === 0) return null;

  return (
    <div className="font-mono text-[12.5px] leading-relaxed whitespace-pre-wrap text-foreground">
      {segments.map((seg, i) =>
        seg.findings.length === 0 ? (
          <span key={i}>{seg.text}</span>
        ) : (
          <Tooltip key={i}>
            <TooltipTrigger
              render={
                <mark className="cursor-default rounded-[3px] bg-warning-soft px-0.5 text-foreground underline decoration-warning decoration-2 underline-offset-2" />
              }
            >
              {seg.text}
            </TooltipTrigger>
            <TooltipContent className="max-w-80">
              <div className="space-y-1">
                {seg.findings.map((f, j) => (
                  <div key={j}>
                    <span className="font-semibold">{categoryLabel(f.category)}</span> ({f.recognizer}),{" "}
                    {formatConfidence(f.confidence)} confidence
                    {f.checksum_valid !== null && f.checksum_valid !== undefined && (
                      <> - checksum {f.checksum_valid ? "valid" : "invalid"}</>
                    )}
                  </div>
                ))}
              </div>
            </TooltipContent>
          </Tooltip>
        ),
      )}
    </div>
  );
}
