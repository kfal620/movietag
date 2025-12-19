/* eslint-disable @next/next/no-img-element */
"use client";

import { useMemo, useState } from "react";
import { Frame, Prediction } from "../lib/types";
import { FrameDetailsPanel } from "../components/FrameDetailsPanel";
import { FrameGrid } from "../components/FrameGrid";
import { OverrideForm } from "../components/OverrideForm";
import { Toolbar } from "../components/Toolbar";

const mockFrames: Frame[] = [
  {
    id: "frame-1",
    movieTitle: "Blade Runner 2049",
    imageUrl:
      "https://images.unsplash.com/photo-1505685296765-3a2736de412f?auto=format&fit=crop&w=1200&q=80",
    sceneTime: "00:34:21",
    ingestSource: "Curated stills",
    predictions: [
      { source: "clip", title: "Blade Runner 2049", confidence: 0.86, year: 2017 },
      { source: "vision-transformer", title: "Dune", confidence: 0.11, year: 2021 },
      { source: "resnet-152", title: "Arrival", confidence: 0.03, year: 2016 },
    ],
    approvedPrediction: { source: "clip", title: "Blade Runner 2049", confidence: 0.86, year: 2017 },
    status: "confirmed",
    tags: ["neon", "cyberpunk"],
  },
  {
    id: "frame-2",
    movieTitle: "Mad Max: Fury Road",
    imageUrl:
      "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1200&q=80",
    sceneTime: "01:12:03",
    ingestSource: "S3 ingest",
    predictions: [
      { source: "clip", title: "Mad Max: Fury Road", confidence: 0.64, year: 2015 },
      { source: "vision-transformer", title: "The Road", confidence: 0.21, year: 2009 },
      { source: "resnet-152", title: "Oblivion", confidence: 0.08, year: 2013 },
    ],
    status: "needs_review",
    notes: "High dust content; model likely misfires on silhouettes.",
    tags: ["action", "desert"],
  },
  {
    id: "frame-3",
    movieTitle: "Inception",
    imageUrl:
      "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=1200&q=80",
    sceneTime: "00:18:11",
    ingestSource: "Framegrab daemon",
    predictions: [
      { source: "clip", title: "Inception", confidence: 0.55, year: 2010 },
      { source: "vision-transformer", title: "Tenet", confidence: 0.33, year: 2020 },
      { source: "resnet-152", title: "The Dark Knight", confidence: 0.07, year: 2008 },
    ],
    status: "overridden",
    overrideTitle: "Inception (2010)",
    tags: ["heist", "mind-bending"],
  },
  {
    id: "frame-4",
    movieTitle: "Interstellar",
    imageUrl:
      "https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=1200&q=80",
    sceneTime: "02:08:49",
    ingestSource: "Curated stills",
    predictions: [
      { source: "clip", title: "Interstellar", confidence: 0.34, year: 2014 },
      { source: "vision-transformer", title: "Gravity", confidence: 0.31, year: 2013 },
      { source: "resnet-152", title: "The Martian", confidence: 0.23, year: 2015 },
    ],
    status: "new",
    tags: ["space", "time-dilation"],
  },
];

const statusFilters: { label: string; value: Frame["status"] | "all" }[] = [
  { label: "All", value: "all" },
  { label: "New", value: "new" },
  { label: "Needs review", value: "needs_review" },
  { label: "Confirmed", value: "confirmed" },
  { label: "Overridden", value: "overridden" },
];

export default function Home() {
  const [frames, setFrames] = useState<Frame[]>(mockFrames);
  const [selectedFrameId, setSelectedFrameId] = useState<string | undefined>(mockFrames[0]?.id);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<Frame["status"] | "all">("all");

  const filteredFrames = useMemo(() => {
    return frames.filter((frame) => {
      const matchesSearch =
        frame.movieTitle.toLowerCase().includes(search.toLowerCase()) ||
        frame.predictions.some((prediction) =>
          prediction.title.toLowerCase().includes(search.toLowerCase()),
        );
      const matchesStatus = statusFilter === "all" ? true : frame.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [frames, search, statusFilter]);

  const selectedFrame = frames.find((frame) => frame.id === selectedFrameId);

  const applyOverride = (frameId: string, prediction: Prediction | string) => {
    setFrames((current) =>
      current.map((frame) => {
        if (frame.id !== frameId) return frame;

        if (typeof prediction === "string") {
          return {
            ...frame,
            overrideTitle: prediction,
            status: "overridden",
          };
        }

        return {
          ...frame,
          approvedPrediction: prediction,
          overrideTitle: undefined,
          status: "confirmed",
        };
      }),
    );
  };

  const refreshFeed = () => {
    // Placeholder for future API fetch; reusing the mock data for now.
    setFrames(mockFrames);
  };

  return (
    <main className="page">
      <Toolbar total={frames.length} onRefresh={refreshFeed}>
        <label className="label" style={{ margin: 0 }}>
          Status
        </label>
        <select
          className="select"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as Frame["status"] | "all")}
        >
          {statusFilters.map((filter) => (
            <option key={filter.value} value={filter.value}>
              {filter.label}
            </option>
          ))}
        </select>
        <input
          className="input"
          placeholder="Search by movie or prediction..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          style={{ minWidth: 240 }}
        />
      </Toolbar>

      <div className="page__content">
        <section className="panel" aria-label="Frame grid">
          <FrameGrid
            frames={filteredFrames}
            selectedId={selectedFrameId}
            onSelect={setSelectedFrameId}
          />
        </section>
        <aside className="panel" aria-label="Frame details">
          <FrameDetailsPanel frame={selectedFrame} />
          <OverrideForm frame={selectedFrame} onApply={applyOverride} />
        </aside>
      </div>
    </main>
  );
}
