"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";

import { getJob, type JobResponse, type JobStatus, type TaskType } from "@/lib/api";
import { cn } from "@/lib/utils";

export type TrackedJobSeed = {
  job_id: string;
  task_type: TaskType;
};

type JobBoardProps = {
  trackedJobs: TrackedJobSeed[];
};

type DisplayJob = JobResponse;

const STATUS_COLUMNS: Array<{
  id: "queued" | "processing" | "done";
  title: string;
  statuses: JobStatus[];
}> = [
  { id: "queued", title: "Queued", statuses: ["QUEUED"] },
  { id: "processing", title: "Processing", statuses: ["PROCESSING"] },
  { id: "done", title: "Done / Failed", statuses: ["SUCCESS", "FAILED"] },
];

function fallbackJob(seed: TrackedJobSeed): DisplayJob {
  const now = new Date().toISOString();
  return {
    job_id: seed.job_id,
    task_type: seed.task_type,
    status: "QUEUED",
    retry_count: 0,
    created_at: now,
    updated_at: now,
    worker_id: null,
    error_msg: null,
  };
}

function JobPoller({
  jobId,
  onUpdate,
}: {
  jobId: string;
  onUpdate: (job: JobResponse) => void;
}) {
  const { data } = useSWR(["job", jobId], () => getJob(jobId), {
    refreshInterval: 2000,
    revalidateOnFocus: true,
    shouldRetryOnError: true,
  });

  useEffect(() => {
    if (data) onUpdate(data);
  }, [data, onUpdate]);

  return null;
}

function statusBorder(status: JobStatus) {
  if (status === "SUCCESS") return "border-l-green-400";
  if (status === "FAILED") return "border-l-red-400";
  if (status === "PROCESSING") return "border-l-amber-400";
  return "border-l-zinc-700";
}

function JobCard({ job }: { job: DisplayJob }) {
  const shortId = job.job_id.slice(0, 8);
  const workerSuffix = job.worker_id?.slice(-12);
  const failed = job.status === "FAILED";

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.18, ease: "easeOut" }}
      className={cn(
        "rounded-lg border border-zinc-900 border-l-2 bg-surface-raised p-3",
        statusBorder(job.status),
      )}
    >
      <div className="mb-3 flex items-start justify-between gap-3">
        <code className="font-mono text-sm text-white">{shortId}</code>
        <span className="rounded-lg border border-zinc-800 bg-zinc-950 px-2 py-0.5 text-[11px] text-zinc-400">
          {job.task_type}
        </span>
      </div>

      <div className="flex flex-col gap-1 text-xs text-zinc-500">
        <div className="flex items-center justify-between gap-3">
          <span>Status</span>
          <span
            className={cn(
              "font-medium text-zinc-300",
              job.status === "SUCCESS" && "text-green-400",
              job.status === "FAILED" && "text-red-400",
              job.status === "PROCESSING" && "text-amber-400",
            )}
          >
            {job.status}
          </span>
        </div>

        {job.retry_count > 0 ? (
          <div className="flex items-center justify-between gap-3 text-amber-400">
            <span>Retries</span>
            <span className="font-medium">{job.retry_count}</span>
          </div>
        ) : null}

        {workerSuffix && job.status === "PROCESSING" ? (
          <div className="flex items-center justify-between gap-3">
            <span>Worker</span>
            <code className="max-w-36 truncate font-mono text-zinc-300">
              {workerSuffix}
            </code>
          </div>
        ) : null}

        {failed && job.error_msg ? (
          <p className="line-clamp-2 text-red-400">{job.error_msg}</p>
        ) : null}
      </div>
    </motion.div>
  );
}

export function JobBoard({ trackedJobs }: JobBoardProps) {
  const [jobsById, setJobsById] = useState<Record<string, JobResponse>>({});

  const trackedIds = useMemo(
    () => trackedJobs.map((job) => job.job_id),
    [trackedJobs],
  );

  useEffect(() => {
    setJobsById((current) => {
      const keep = new Set(trackedIds);
      return Object.fromEntries(
        Object.entries(current).filter(([jobId]) => keep.has(jobId)),
      );
    });
  }, [trackedIds]);

  const updateJob = (job: JobResponse) => {
    setJobsById((current) => ({
      ...current,
      [job.job_id]: job,
    }));
  };

  const displayJobs = trackedJobs.map(
    (seed) => jobsById[seed.job_id] ?? fallbackJob(seed),
  );

  return (
    <section className="flex flex-col gap-4">
      {trackedIds.map((jobId) => (
        <JobPoller key={jobId} jobId={jobId} onUpdate={updateJob} />
      ))}

      <div className="flex items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-medium text-white">Live Job Board</h2>
          <p className="text-xs text-zinc-500">
            {trackedJobs.length.toLocaleString()} tracked this session
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        {STATUS_COLUMNS.map((column) => {
          const jobs = displayJobs.filter((job) =>
            column.statuses.includes(job.status),
          );

          return (
            <div
              key={column.id}
              className="flex min-h-80 flex-col rounded-lg border border-zinc-900 bg-surface p-3"
            >
              <div className="mb-3 flex items-center justify-between">
                <h3 className="text-sm font-medium text-white">{column.title}</h3>
                <span className="rounded-lg border border-zinc-800 px-2 py-0.5 text-xs text-zinc-500">
                  {jobs.length}
                </span>
              </div>

              <div className="flex flex-1 flex-col gap-2">
                <AnimatePresence initial={false}>
                  {jobs.map((job) => (
                    <JobCard key={job.job_id} job={job} />
                  ))}
                </AnimatePresence>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
