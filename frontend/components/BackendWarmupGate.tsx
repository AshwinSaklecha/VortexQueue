"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Server,
  Wifi,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { Button } from "@/components/ui/button";
import { checkBackendReady, type DashboardStats } from "@/lib/api";
import { cn } from "@/lib/utils";

type BackendWarmupGateProps = {
  children: ReactNode;
  onReady?: (stats: DashboardStats) => void;
};

const REQUEST_TIMEOUT_MS = 12000;
const RETRY_DELAY_MS = 2500;

const WAIT_STATES = [
  {
    after: 0,
    title: "Please wait, the backend is loading.",
    detail:
      "Free Render instances pause when idle. I am waking the API before opening the dashboard.",
  },
  {
    after: 12,
    title: "Starting backend services.",
    detail: "Utilities are loading and startup scripts may still be running.",
  },
  {
    after: 28,
    title: "Almost there.",
    detail:
      "The warm-up request is still active. The dashboard will appear as soon as the API responds.",
  },
  {
    after: 50,
    title: "Still warming up.",
    detail:
      "Free-tier cold starts can take a little while after the server has been idle.",
  },
  {
    after: 90,
    title: "Taking longer than usual.",
    detail: "I will keep retrying automatically until the backend is reachable.",
  },
];

const STEPS = [
  {
    label: "Wake signal",
    detail: "Pinging the API",
    icon: Server,
  },
  {
    label: "Runtime boot",
    detail: "Loading services",
    icon: Activity,
  },
  {
    label: "Dashboard handoff",
    detail: "Waiting for data",
    icon: Wifi,
  },
];

function formatElapsed(totalSeconds: number) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;

  if (minutes === 0) {
    return `${seconds}s`;
  }

  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

export function BackendWarmupGate({
  children,
  onReady,
}: BackendWarmupGateProps) {
  const [isReady, setIsReady] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [attempts, setAttempts] = useState(0);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const mountedRef = useRef(false);
  const readyRef = useRef(false);
  const checkingRef = useRef(false);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onReadyRef = useRef(onReady);

  useEffect(() => {
    onReadyRef.current = onReady;
  }, [onReady]);

  const waitState = useMemo(() => {
    return WAIT_STATES.reduce((current, item) => {
      return elapsedSeconds >= item.after ? item : current;
    }, WAIT_STATES[0]);
  }, [elapsedSeconds]);

  const runCheck = useCallback(async () => {
    if (checkingRef.current || readyRef.current) return;

    checkingRef.current = true;
    setIsChecking(true);
    setAttempts((current) => current + 1);

    try {
      const stats = await checkBackendReady({ timeoutMs: REQUEST_TIMEOUT_MS });
      if (!mountedRef.current) return;

      readyRef.current = true;
      onReadyRef.current?.(stats);
      setIsReady(true);
    } catch {
      if (!mountedRef.current || readyRef.current) return;

      retryTimerRef.current = setTimeout(() => {
        void runCheck();
      }, RETRY_DELAY_MS);
    } finally {
      checkingRef.current = false;
      if (mountedRef.current && !readyRef.current) {
        setIsChecking(false);
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    const startedAt = Date.now();
    const elapsedTimer = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    void runCheck();

    return () => {
      mountedRef.current = false;
      clearInterval(elapsedTimer);
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
      }
    };
  }, [runCheck]);

  function retryNow() {
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }

    void runCheck();
  }

  return (
    <AnimatePresence mode="wait">
      {isReady ? (
        <motion.div
          key="dashboard"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
        >
          {children}
        </motion.div>
      ) : (
        <motion.main
          key="warmup"
          className="min-h-screen bg-background text-white"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.28, ease: "easeOut" }}
        >
          <div className="mx-auto flex min-h-screen w-full max-w-5xl flex-col px-4 py-5 sm:px-6 lg:px-8">
            <header className="flex min-h-14 items-center justify-between border-b border-zinc-900">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-zinc-800 bg-surface-raised">
                  <Activity className="h-4 w-4 text-white" aria-hidden="true" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-white">VortexQueue</p>
                  <p className="text-xs text-zinc-500">API warm-up</p>
                </div>
              </div>

              <div className="hidden items-center gap-2 text-xs text-zinc-500 sm:flex">
                <span
                  className={cn(
                    "h-2 w-2 rounded-full bg-amber-400",
                    isChecking && "animate-pulse",
                  )}
                />
                Waking backend
              </div>
            </header>

            <section className="flex flex-1 items-center justify-center py-12">
              <div className="w-full max-w-2xl" role="status" aria-live="polite">
                <div className="mb-8 flex items-center gap-4">
                  <div className="relative h-16 w-16 shrink-0">
                    <div className="absolute inset-0 rounded-full border border-zinc-800 bg-surface" />
                    <motion.div
                      className="absolute inset-0 rounded-full border border-transparent border-r-emerald-300 border-t-white"
                      animate={{ rotate: 360 }}
                      transition={{
                        duration: 1.4,
                        ease: "linear",
                        repeat: Infinity,
                      }}
                    />
                    <div className="absolute inset-2 flex items-center justify-center rounded-full bg-zinc-950">
                      <Loader2
                        className="h-5 w-5 animate-spin text-zinc-300"
                        aria-hidden="true"
                      />
                    </div>
                  </div>

                  <div>
                    <p className="mb-2 text-xs font-medium uppercase tracking-[0.18em] text-emerald-300">
                      Cold start in progress
                    </p>
                    <h1 className="text-3xl font-semibold tracking-normal text-white sm:text-4xl">
                      {waitState.title}
                    </h1>
                  </div>
                </div>

                <p className="max-w-xl text-sm leading-6 text-zinc-400 sm:text-base">
                  {waitState.detail}
                </p>

                <div className="mt-8 overflow-hidden rounded-full border border-zinc-800 bg-zinc-950">
                  <motion.div
                    className="h-1.5 w-1/3 rounded-full bg-gradient-to-r from-white via-emerald-300 to-cyan-300"
                    animate={{ x: ["-120%", "320%"] }}
                    transition={{
                      duration: 1.7,
                      ease: "easeInOut",
                      repeat: Infinity,
                    }}
                  />
                </div>

                <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
                  {STEPS.map((step, index) => {
                    const Icon = step.icon;
                    const active = index === Math.min(2, Math.floor(elapsedSeconds / 14));
                    const complete = index < Math.min(2, Math.floor(elapsedSeconds / 14));

                    return (
                      <div
                        key={step.label}
                        className={cn(
                          "rounded-lg border border-zinc-900 bg-surface p-3 transition-colors",
                          active && "border-zinc-700",
                          complete && "border-emerald-900/80",
                        )}
                      >
                        <div className="mb-3 flex items-center justify-between gap-2">
                          <Icon
                            className={cn(
                              "h-4 w-4 text-zinc-500",
                              active && "text-white",
                              complete && "text-emerald-300",
                            )}
                            aria-hidden="true"
                          />
                          {complete ? (
                            <CheckCircle2
                              className="h-4 w-4 text-emerald-300"
                              aria-hidden="true"
                            />
                          ) : null}
                        </div>
                        <p className="text-sm font-medium text-white">
                          {step.label}
                        </p>
                        <p className="mt-1 text-xs text-zinc-500">{step.detail}</p>
                      </div>
                    );
                  })}
                </div>

                <div className="mt-6 flex flex-col gap-3 border-t border-zinc-900 pt-5 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-zinc-500">
                    Attempt {attempts.toLocaleString()} · elapsed{" "}
                    {formatElapsed(elapsedSeconds)}
                  </p>

                  <Button
                    type="button"
                    variant="secondary"
                    onClick={retryNow}
                    disabled={isChecking}
                  >
                    <RefreshCw
                      className={cn("h-4 w-4", isChecking && "animate-spin")}
                      aria-hidden="true"
                    />
                    {isChecking ? "Checking" : "Retry now"}
                  </Button>
                </div>
              </div>
            </section>
          </div>
        </motion.main>
      )}
    </AnimatePresence>
  );
}
