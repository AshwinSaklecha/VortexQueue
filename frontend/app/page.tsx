"use client";

import { useCallback, useState } from "react";
import useSWR from "swr";

import { ControlBar } from "@/components/ControlBar";
import { JobBoard, type TrackedJobSeed } from "@/components/JobBoard";
import { MetricsGrid } from "@/components/MetricsGrid";
import { ThroughputChart } from "@/components/ThroughputChart";
import { getDashboardStats } from "@/lib/api";

const MAX_TRACKED_JOBS = 100;

export default function DashboardPage() {
  const [trackedJobs, setTrackedJobs] = useState<TrackedJobSeed[]>([]);

  const {
    data: stats,
    error: statsError,
    isValidating,
  } = useSWR("dashboard-stats", getDashboardStats, {
    refreshInterval: 2000,
    revalidateOnFocus: true,
    keepPreviousData: true,
  });

  const addTrackedJobs = useCallback((jobs: TrackedJobSeed[]) => {
    setTrackedJobs((current) => {
      const seen = new Set<string>();
      return [...jobs, ...current]
        .filter((job) => {
          if (seen.has(job.job_id)) return false;
          seen.add(job.job_id);
          return true;
        })
        .slice(0, MAX_TRACKED_JOBS);
    });
  }, []);

  return (
    <main className="min-h-screen bg-background text-white">
      <ControlBar
        isLive={isValidating && !statsError}
        onJobsCreated={addTrackedJobs}
      />

      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 pb-10 pt-6 sm:px-6 lg:px-8">
        <section className="flex flex-col gap-4">
          <MetricsGrid stats={stats} />
          <ThroughputChart stats={stats} />
        </section>

        <JobBoard trackedJobs={trackedJobs} />
      </div>
    </main>
  );
}
