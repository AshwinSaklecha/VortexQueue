"use client";

import { useEffect, useRef } from "react";
import { X, Download } from "lucide-react";
import {
  type JobResponse,
  type ImageResult,
  type ScrapingResult,
  type InvoiceResult,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type JobResultModalProps = {
  job: JobResponse;
  onClose: () => void;
};

export function JobResultModal({ job, onClose }: JobResultModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  function handleOverlayClick(e: React.MouseEvent) {
    if (e.target === overlayRef.current) onClose();
  }

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
    >
      <div className="relative flex max-h-[90vh] w-full max-w-2xl flex-col rounded-xl border border-zinc-800 bg-[#111111] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-900 px-5 py-4">
          <div>
            <p className="text-sm font-medium text-white">Job Result</p>
            <p className="text-xs text-zinc-500">
              <code className="font-mono">{job.job_id.slice(0, 8)}</code>
              {" · "}
              {job.task_type}
            </p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-zinc-500 hover:bg-zinc-900 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <div className="overflow-y-auto p-5">
          {job.task_type === "web_scraping" && job.result && (
            <ScrapingResultView result={job.result as ScrapingResult} />
          )}
          {job.task_type === "image_processing" && job.result && (
            <ImageResultView result={job.result as ImageResult} jobId={job.job_id} />
          )}
          {job.task_type === "bulk_invoice" && job.result && (
            <InvoiceResultView result={job.result as InvoiceResult} />
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Web scraping result
// ---------------------------------------------------------------------------

function ScrapingResultView({ result }: { result: ScrapingResult }) {
  const entries = Object.entries(result.scraped);
  const total = entries.reduce((sum, [, vals]) => sum + vals.length, 0);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2">
        <span className="text-xs text-zinc-500">Source:</span>
        <a
          href={result.url}
          target="_blank"
          rel="noopener noreferrer"
          className="truncate text-xs text-white underline decoration-zinc-600 hover:decoration-white"
        >
          {result.url}
        </a>
      </div>
      <p className="text-xs text-zinc-500">{total} matches across {entries.length} selector(s)</p>

      {entries.map(([selector, values]) => (
        <div key={selector}>
          <p className="mb-1.5 font-mono text-xs text-zinc-400">{selector}</p>
          <div className="flex flex-col gap-1 rounded-lg border border-zinc-900 bg-zinc-950 p-3">
            {values.length === 0 ? (
              <p className="text-xs text-zinc-600">No matches</p>
            ) : (
              values.slice(0, 20).map((v, i) => (
                <p key={i} className="text-sm text-zinc-300 leading-relaxed">
                  {v}
                </p>
              ))
            )}
            {values.length > 20 && (
              <p className="text-xs text-zinc-600">+{values.length - 20} more</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Image result
// ---------------------------------------------------------------------------

function ImageResultView({ result, jobId }: { result: ImageResult; jobId: string }) {
  function downloadImage() {
    const link = document.createElement("a");
    link.href = `data:image/png;base64,${result.image_b64}`;
    link.download = `processed_${jobId.slice(0, 8)}.png`;
    link.click();
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Original" value={`${result.original_size[0]}×${result.original_size[1]}`} />
        <Stat label="Final" value={`${result.final_size[0]}×${result.final_size[1]}`} />
        <Stat label="Mode" value={result.mode} />
      </div>

      {result.operations_applied.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {result.operations_applied.map((op) => (
            <span
              key={op}
              className="rounded border border-zinc-800 bg-zinc-950 px-2 py-0.5 text-xs text-zinc-400"
            >
              {op}
            </span>
          ))}
        </div>
      )}

      {/* Image preview */}
      <div className="overflow-hidden rounded-lg border border-zinc-900 bg-zinc-950">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`data:image/png;base64,${result.image_b64}`}
          alt="Processed image"
          className="max-h-80 w-full object-contain"
        />
      </div>

      <button
        onClick={downloadImage}
        className="flex items-center justify-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-2.5 text-sm text-white transition-colors hover:border-zinc-600"
      >
        <Download className="h-4 w-4" />
        Download PNG
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Invoice result
// ---------------------------------------------------------------------------

function InvoiceResultView({ result }: { result: InvoiceResult }) {
  function downloadPdf() {
    const bytes = atob(result.pdf_b64);
    const arr = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
    const blob = new Blob([arr], { type: "application/pdf" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = result.filename;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3">
        <Stat label="Total" value={`$${result.total.toFixed(2)}`} />
        <Stat label="Line items" value={String(result.items_count)} />
      </div>

      <div className="rounded-lg border border-zinc-900 bg-zinc-950 p-4">
        <p className="text-xs text-zinc-500">Invoice generated for</p>
        <p className="mt-1 text-sm text-white">{result.email}</p>
      </div>

      <button
        onClick={downloadPdf}
        className="flex items-center justify-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950 px-4 py-2.5 text-sm text-white transition-colors hover:border-zinc-600"
      >
        <Download className="h-4 w-4" />
        Download PDF — {result.filename}
      </button>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-zinc-900 bg-zinc-950 p-3">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className="mt-1 text-sm font-medium text-white">{value}</p>
    </div>
  );
}
