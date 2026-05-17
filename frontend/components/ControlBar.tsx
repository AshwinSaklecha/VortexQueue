"use client";

import { Activity, Plus, Zap } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  buildDemoJob,
  createJob,
  getRandomTaskType,
  TASK_TYPES,
  type TaskType,
} from "@/lib/api";
import type { TrackedJobSeed } from "@/lib/api";
import { cn } from "@/lib/utils";

type ControlBarProps = {
  isLive: boolean;
  onJobsCreated: (jobs: TrackedJobSeed[]) => void;
};

export function ControlBar({ isLive, onJobsCreated }: ControlBarProps) {
  const [isSpawning, setIsSpawning] = useState(false);
  const [isStressTesting, setIsStressTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function spawnOne() {
    setIsSpawning(true);
    setError(null);

    try {
      const taskType = getRandomTaskType();
      const job = buildDemoJob(taskType);
      const response = await createJob(job.task_type, job.payload);
      onJobsCreated([{ job_id: response.job_id, task_type: taskType }]);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Failed to spawn job");
    } finally {
      setIsSpawning(false);
    }
  }

  async function stressTest() {
    setIsStressTesting(true);
    setError(null);

    try {
      const created = await Promise.all(
        Array.from({ length: 50 }, async (_, index) => {
          const taskType = TASK_TYPES[index % TASK_TYPES.length] as TaskType;
          const job = buildDemoJob(taskType);
          const response = await createJob(job.task_type, job.payload);
          return { job_id: response.job_id, task_type: taskType };
        }),
      );
      onJobsCreated(created.reverse());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Stress test failed");
    } finally {
      setIsStressTesting(false);
    }
  }

  return (
    <header className="sticky top-0 z-40 border-b border-zinc-900 bg-background/95 backdrop-blur">
      <div className="mx-auto flex min-h-16 w-full max-w-7xl flex-col gap-3 px-4 py-3 sm:px-6 lg:flex-row lg:items-center lg:justify-between lg:px-8">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-800 bg-surface-raised">
            <Activity className="h-4 w-4 text-white" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-base font-semibold tracking-normal text-white">
              VortexQueue
            </h1>
            {error ? (
              <p className="max-w-xl truncate text-xs text-red-400">{error}</p>
            ) : null}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={spawnOne} disabled={isSpawning || isStressTesting}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            {isSpawning ? "Spawning" : "Spawn Job"}
          </Button>

          <Button
            variant="secondary"
            onClick={stressTest}
            disabled={isSpawning || isStressTesting}
          >
            <Zap className="h-4 w-4" aria-hidden="true" />
            {isStressTesting ? "Firing" : "Stress Test x50"}
          </Button>

          <div className="flex h-9 items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm text-zinc-300">
            <span
              className={cn(
                "h-2 w-2 rounded-full bg-zinc-600",
                isLive && "animate-pulse bg-green-400",
              )}
            />
            Live
          </div>
        </div>
      </div>
    </header>
  );
}
