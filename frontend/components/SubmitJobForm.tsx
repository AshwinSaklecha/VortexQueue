"use client";

import { useState } from "react";
import { createJob, type TaskType, type TrackedJobSeed } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { ChevronDown, ChevronUp, Send } from "lucide-react";

type SubmitJobFormProps = {
  onJobCreated: (job: TrackedJobSeed) => void;
};

const TASK_LABELS: Record<TaskType, string> = {
  image_processing: "Image Processing",
  web_scraping: "Web Scraping",
  bulk_invoice: "Bulk Invoice",
};

const DEFAULT_LINE_ITEM = { name: "", qty: 1, unit_price: 0 };

export function SubmitJobForm({ onJobCreated }: SubmitJobFormProps) {
  const [open, setOpen] = useState(false);
  const [taskType, setTaskType] = useState<TaskType>("web_scraping");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // web_scraping fields
  const [scrapeUrl, setScrapeUrl] = useState("https://news.ycombinator.com");
  const [scrapeSelectors, setScrapeSelectors] = useState("a.storylink, .score");

  // image_processing fields
  const [imageUrl, setImageUrl] = useState("https://picsum.photos/800/600");
  const [imgOps, setImgOps] = useState<Record<string, boolean>>({
    resize: true,
    grayscale: true,
    watermark: false,
  });

  // bulk_invoice fields
  const [customerId, setCustomerId] = useState("CUST-001");
  const [email, setEmail] = useState("demo@example.com");
  const [lineItems, setLineItems] = useState([
    { name: "Widget Pro", qty: 2, unit_price: 49.99 },
    { name: "Support Plan", qty: 1, unit_price: 199.0 },
  ]);

  function buildPayload() {
    if (taskType === "web_scraping") {
      const selectors = scrapeSelectors
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      return { url: scrapeUrl, selectors };
    }
    if (taskType === "image_processing") {
      const operations = Object.entries(imgOps)
        .filter(([, v]) => v)
        .map(([k]) => k);
      return { image_url: imageUrl, operations };
    }
    // bulk_invoice
    return {
      customer_id: customerId,
      email,
      line_items: lineItems.map((item) => ({
        name: item.name,
        qty: Number(item.qty),
        unit_price: Number(item.unit_price),
      })),
    };
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const payload = buildPayload();
      const response = await createJob(taskType, payload);
      onJobCreated({ job_id: response.job_id, task_type: taskType });
      setOpen(false);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  }

  function updateLineItem(
    index: number,
    field: keyof (typeof lineItems)[0],
    value: string | number,
  ) {
    setLineItems((items) =>
      items.map((item, i) => (i === index ? { ...item, [field]: value } : item)),
    );
  }

  return (
    <div className="rounded-lg border border-zinc-900 bg-surface">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <div>
          <p className="text-sm font-medium text-white">Submit Custom Job</p>
          <p className="text-xs text-zinc-500">
            Choose task type, fill in your own inputs, get real output back
          </p>
        </div>
        {open ? (
          <ChevronUp className="h-4 w-4 shrink-0 text-zinc-500" />
        ) : (
          <ChevronDown className="h-4 w-4 shrink-0 text-zinc-500" />
        )}
      </button>

      {open && (
        <form onSubmit={handleSubmit} className="border-t border-zinc-900 p-4">
          {/* Task type tabs */}
          <div className="mb-5 flex gap-1 rounded-lg border border-zinc-900 bg-zinc-950 p-1">
            {(Object.keys(TASK_LABELS) as TaskType[]).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTaskType(t)}
                className={cn(
                  "flex-1 rounded px-3 py-1.5 text-xs font-medium transition-colors",
                  taskType === t
                    ? "bg-white text-black"
                    : "text-zinc-400 hover:text-white",
                )}
              >
                {TASK_LABELS[t]}
              </button>
            ))}
          </div>

          {/* Web scraping fields */}
          {taskType === "web_scraping" && (
            <div className="flex flex-col gap-3">
              <Field label="URL to scrape">
                <input
                  type="url"
                  value={scrapeUrl}
                  onChange={(e) => setScrapeUrl(e.target.value)}
                  placeholder="https://example.com"
                  required
                  className={inputCls}
                />
              </Field>
              <Field label="CSS selectors (comma-separated)">
                <input
                  type="text"
                  value={scrapeSelectors}
                  onChange={(e) => setScrapeSelectors(e.target.value)}
                  placeholder="h1, .price, #description"
                  required
                  className={inputCls}
                />
              </Field>
            </div>
          )}

          {/* Image processing fields */}
          {taskType === "image_processing" && (
            <div className="flex flex-col gap-3">
              <Field label="Image URL (max 5 MB)">
                <input
                  type="url"
                  value={imageUrl}
                  onChange={(e) => setImageUrl(e.target.value)}
                  placeholder="https://example.com/image.jpg"
                  required
                  className={inputCls}
                />
              </Field>
              <Field label="Operations">
                <div className="flex flex-wrap gap-3">
                  {(["resize", "grayscale", "watermark"] as const).map((op) => (
                    <label
                      key={op}
                      className="flex cursor-pointer items-center gap-2 text-sm text-zinc-300"
                    >
                      <input
                        type="checkbox"
                        checked={imgOps[op]}
                        onChange={(e) =>
                          setImgOps((prev) => ({ ...prev, [op]: e.target.checked }))
                        }
                        className="accent-white"
                      />
                      {op}
                    </label>
                  ))}
                </div>
              </Field>
            </div>
          )}

          {/* Bulk invoice fields */}
          {taskType === "bulk_invoice" && (
            <div className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Customer ID">
                  <input
                    type="text"
                    value={customerId}
                    onChange={(e) => setCustomerId(e.target.value)}
                    required
                    className={inputCls}
                  />
                </Field>
                <Field label="Email">
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className={inputCls}
                  />
                </Field>
              </div>

              <Field label="Line items">
                <div className="flex flex-col gap-2">
                  {lineItems.map((item, i) => (
                    <div key={i} className="flex gap-2">
                      <input
                        type="text"
                        value={item.name}
                        onChange={(e) => updateLineItem(i, "name", e.target.value)}
                        placeholder="Item name"
                        className={cn(inputCls, "flex-1")}
                      />
                      <input
                        type="number"
                        value={item.qty}
                        onChange={(e) => updateLineItem(i, "qty", e.target.value)}
                        placeholder="Qty"
                        min={1}
                        className={cn(inputCls, "w-16")}
                      />
                      <input
                        type="number"
                        value={item.unit_price}
                        onChange={(e) => updateLineItem(i, "unit_price", e.target.value)}
                        placeholder="Price"
                        min={0}
                        step={0.01}
                        className={cn(inputCls, "w-24")}
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setLineItems((items) => items.filter((_, j) => j !== i))
                        }
                        className="px-2 text-zinc-500 hover:text-red-400"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() =>
                      setLineItems((items) => [...items, { ...DEFAULT_LINE_ITEM }])
                    }
                    className="text-left text-xs text-zinc-500 hover:text-white"
                  >
                    + Add item
                  </button>
                </div>
              </Field>
            </div>
          )}

          {error && (
            <p className="mt-3 text-xs text-red-400">{error}</p>
          )}

          <div className="mt-4 flex justify-end">
            <Button type="submit" disabled={submitting}>
              <Send className="h-4 w-4" />
              {submitting ? "Submitting…" : "Submit Job"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs text-zinc-500">{label}</label>
      {children}
    </div>
  );
}

const inputCls =
  "rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-white placeholder-zinc-600 outline-none focus:border-zinc-600";
