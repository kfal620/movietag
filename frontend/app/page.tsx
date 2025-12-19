/* eslint-disable @next/next/no-img-element */
"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { Frame, Prediction } from "../lib/types";
import { FrameDetailsPanel } from "../components/FrameDetailsPanel";
import { FrameGrid } from "../components/FrameGrid";
import { OverrideForm } from "../components/OverrideForm";
import { Toolbar } from "../components/Toolbar";

const statusFilters: { label: string; value: Frame["status"] | "all" }[] = [
  { label: "All", value: "all" },
  { label: "New", value: "new" },
  { label: "Needs review", value: "needs_review" },
  { label: "Confirmed", value: "confirmed" },
  { label: "Overridden", value: "overridden" },
  { label: "Tagged", value: "tagged" },
];

type FrameApiItem = {
  id: number;
  movie_id: number;
  status: Frame["status"];
  signed_url?: string;
  file_path: string;
  tags?: { name: string }[];
  scene_attributes?: { attribute: string; value: string; confidence?: number }[];
};

type FramesApiResponse = { items: FrameApiItem[]; total: number };

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function Home() {
  const { data, mutate } = useSWR<FramesApiResponse>("/api/frames", fetcher, {
    revalidateOnFocus: false,
  });

  const frames: Frame[] =
    data?.items.map((item) => ({
      id: item.id,
      movieId: item.movie_id,
      movieTitle: `Movie #${item.movie_id}`,
      imageUrl:
        item.signed_url ||
        "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=900&q=60",
      predictions: [],
      status: item.status,
      tags: item.tags?.map((tag) => tag.name) ?? [],
      sceneAttributes: item.scene_attributes,
    })) ?? [];

  const [selectedFrameId, setSelectedFrameId] = useState<number | undefined>(frames[0]?.id);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<Frame["status"] | "all">("all");

  const filteredFrames = useMemo(() => {
    return frames.filter((frame) => {
      const matchesSearch =
        frame.movieTitle.toLowerCase().includes(search.toLowerCase()) ||
        frame.tags?.some((tag) => tag.toLowerCase().includes(search.toLowerCase()));
      const matchesStatus = statusFilter === "all" ? true : frame.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [frames, search, statusFilter]);

  const selectedFrame = frames.find((frame) => frame.id === selectedFrameId);

  const applyOverride = (frameId: number, prediction: Prediction | string) => {
    const payload =
      typeof prediction === "string"
        ? { tags: [prediction] }
        : { tags: [prediction.title] };
    fetch(`/api/frames/${frameId}/tags`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(() => mutate());
  };

  const refreshFeed = () => {
    mutate();
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
          placeholder="Search by movie or tags..."
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          style={{ minWidth: 240 }}
        />
      </Toolbar>

      <div className="page__content">
        <section className="panel" aria-label="Frame grid">
          <FrameGrid frames={filteredFrames} selectedId={selectedFrameId} onSelect={setSelectedFrameId} />
        </section>
        <aside className="panel" aria-label="Frame details">
          <FrameDetailsPanel frame={selectedFrame} />
          <OverrideForm frame={selectedFrame} onApply={applyOverride} />
        </aside>
      </div>
    </main>
  );
}
