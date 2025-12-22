import Image from "next/image";
import { useState } from "react";
import { ActorDetection, Frame, Prediction, SceneAttribute } from "../lib/types";
import { FrameDetailsPanel } from "./FrameDetailsPanel";
import { FrameEditPanel } from "./FrameEditPanel";

type Props = {
    frame?: Frame;
    onSaveMetadata: (frameId: number, updates: Partial<Frame>) => void;
    onApplyOverride: (frameId: number, prediction: Prediction | string) => void;
    onSaveScene: (frameId: number, attributes: SceneAttribute[]) => void;
    onSaveActors: (frameId: number, detections: ActorDetection[]) => void;
    children?: React.ReactNode;
};

export function FrameSidebar({
    frame,
    onSaveMetadata,
    onApplyOverride,
    onSaveScene,
    onSaveActors,
    children,
}: Props) {
    const [mode, setMode] = useState<"view" | "edit">("view");

    if (!frame) {
        return (
            <div className="sidebar">
                <div className="empty-state">
                    Choose a frame from the grid to inspect predictions and metadata.
                </div>
            </div>
        );
    }

    const toggleMode = () => setMode((prev) => (prev === "view" ? "edit" : "view"));

    return (
        <div className="sidebar" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
            {/* Permanent Header */}
            <div className="sidebar__section" style={{ flexShrink: 0 }}>
                <div style={{ position: "relative", width: "100%", height: 200, borderRadius: 12, overflow: "hidden" }}>
                    <Image src={frame.imageUrl} alt={frame.movieTitle} fill style={{ objectFit: "cover" }} />

                    <button
                        onClick={toggleMode}
                        className="button"
                        style={{
                            position: 'absolute',
                            bottom: 8,
                            right: 8,
                            background: 'rgba(0,0,0,0.7)',
                            color: 'white',
                            backdropFilter: 'blur(4px)',
                            border: '1px solid rgba(255,255,255,0.2)'
                        }}
                    >
                        {mode === 'view' ? 'Edit Metadata' : 'Back to View'}
                    </button>
                </div>

                <h3 className="sidebar__title" style={{ marginTop: "0.9rem" }}>
                    {frame.movieTitle}
                </h3>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <p style={{ color: "var(--muted)", marginTop: "0.3rem" }}>Status: {frame.status.replace("_", " ")}</p>
                    {mode === 'edit' && <span className="chip" style={{ background: 'var(--primary)', color: 'white' }}>Editing</span>}
                </div>
            </div>

            {/* Scrollable Content Area */}
            <div style={{ overflowY: "auto", flexGrow: 1 }}>
                {mode === "view" ? (
                    <>
                        <FrameDetailsPanel frame={frame} />
                        {children}
                    </>
                ) : (
                    <FrameEditPanel
                        frame={frame}
                        onSaveMetadata={onSaveMetadata}
                        onApplyOverride={onApplyOverride}
                        onSaveScene={onSaveScene}
                        onSaveActors={onSaveActors}
                    />
                )}
            </div>
        </div>
    );
}
