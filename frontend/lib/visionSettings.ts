/**
 * Vision pipeline settings utilities
 * Manages localStorage for pipeline selection and preferences
 */

const STORAGE_KEY = "movietag:vision:settings";

export interface VisionSettings {
    selectedPipelineId: string;
    autoComputeEnhanced: boolean;
}

const DEFAULT_SETTINGS: VisionSettings = {
    selectedPipelineId: "clip_vitb32", // default to standard pipeline
    autoComputeEnhanced: false,
};

/**
 * Get vision settings from localStorage
 */
export function getVisionSettings(): VisionSettings {
    if (typeof window === "undefined") {
        return DEFAULT_SETTINGS;
    }

    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (!stored) {
            return DEFAULT_SETTINGS;
        }

        const parsed = JSON.parse(stored) as Partial<VisionSettings>;
        return {
            ...DEFAULT_SETTINGS,
            ...parsed,
        };
    } catch (error) {
        console.error("Failed to parse vision settings:", error);
        return DEFAULT_SETTINGS;
    }
}

/**
 * Save vision settings to localStorage
 */
export function saveVisionSettings(settings: Partial<VisionSettings>): void {
    if (typeof window === "undefined") {
        return;
    }

    try {
        const current = getVisionSettings();
        const updated = {
            ...current,
            ...settings,
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
    } catch (error) {
        console.error("Failed to save vision settings:", error);
    }
}

/**
 * Get the currently selected pipeline ID
 */
export function getSelectedPipelineId(): string {
    return getVisionSettings().selectedPipelineId;
}

/**
 * Set the selected pipeline ID
 */
export function setSelectedPipelineId(pipelineId: string): void {
    saveVisionSettings({ selectedPipelineId: pipelineId });
}
