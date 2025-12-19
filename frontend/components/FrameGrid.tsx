import { Frame } from "../lib/types";
import { FrameCard } from "./FrameCard";

type Props = {
  frames: Frame[];
  selectedId?: number;
  onSelect: (id: number) => void;
};

export function FrameGrid({ frames, selectedId, onSelect }: Props) {
  if (!frames.length) {
    return (
      <div className="empty-state">
        No frames matched your filters. Try resetting the search or status selector.
      </div>
    );
  }

  return (
    <div className="grid" role="list">
      {frames.map((frame) => (
        <FrameCard
          key={frame.id}
          frame={frame}
          isActive={frame.id === selectedId}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
