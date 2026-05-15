"use client";

import { Info } from "lucide-react";

import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { DashboardStats } from "@/lib/api";
import { cn } from "@/lib/utils";

type MetricsGridProps = {
  stats?: DashboardStats;
};

type StatCardProps = {
  label: string;
  value: number;
  tone?: "default" | "green" | "amber" | "red";
  glow?: boolean;
  tooltip?: string;
};

function StatCard({ label, value, tone = "default", glow, tooltip }: StatCardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-zinc-900 bg-surface p-4",
        glow && "border-red-900 shadow-[0_0_0_1px_rgba(248,113,113,0.16)]",
      )}
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <p className="text-sm text-zinc-500">{label}</p>
        {tooltip ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                className="inline-flex h-6 w-6 items-center justify-center rounded-lg text-zinc-500 transition-colors hover:bg-zinc-900 hover:text-white"
                type="button"
                aria-label={tooltip}
              >
                <Info className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </TooltipTrigger>
            <TooltipContent>{tooltip}</TooltipContent>
          </Tooltip>
        ) : null}
      </div>
      <p
        className={cn(
          "text-3xl font-semibold tracking-normal text-white",
          tone === "green" && "text-green-400",
          tone === "amber" && "text-amber-400",
          tone === "red" && "text-red-400",
        )}
      >
        {value.toLocaleString()}
      </p>
    </div>
  );
}

export function MetricsGrid({ stats }: MetricsGridProps) {
  const queueDepth = stats?.queue_depth ?? 0;
  const processing = stats?.jobs_by_status.PROCESSING ?? 0;
  const completed = stats?.jobs_by_status.SUCCESS ?? 0;
  const dlqCount = stats?.dlq_count ?? 0;

  return (
    <TooltipProvider>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Queue Depth"
          value={queueDepth}
          tone={queueDepth > 10 ? "red" : "default"}
        />
        <StatCard
          label="Processing"
          value={processing}
          tone={processing > 0 ? "amber" : "default"}
        />
        <StatCard label="Completed" value={completed} tone="green" />
        <StatCard
          label="Dead Letter"
          value={dlqCount}
          tone={dlqCount > 0 ? "red" : "default"}
          glow={dlqCount > 0}
          tooltip="Jobs that failed after max retries"
        />
      </div>
    </TooltipProvider>
  );
}
