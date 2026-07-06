export type MicaBackgroundPreset = {
  id: string;
  label: string;
  description: string;
  url: string;
};

export const CUSTOM_BACKGROUND_STORAGE_KEY = "mica.customBackgroundImage";

export const MICA_BACKGROUND_PRESETS: MicaBackgroundPreset[] = [
  {
    id: "harbor",
    label: "Harbor",
    description: "Dark brick canal with quiet contrast",
    url: "/backgrounds/mica-harbor.jpg",
  },
  {
    id: "valley",
    label: "Valley",
    description: "Soft pink city haze",
    url: "/backgrounds/mica-valley.jpg",
  },
  {
    id: "clouds",
    label: "Clouds",
    description: "Open sky with calm color",
    url: "/backgrounds/mica-clouds.jpg",
  },
  {
    id: "lake",
    label: "Lake",
    description: "Mist, water and mountain glass",
    url: "/backgrounds/mica-lake.jpg",
  },
];

export function getMicaBackgroundUrl(backgroundId?: string | null, backgroundUrl?: string | null) {
  if (backgroundId === "custom") {
    try {
      return window.localStorage.getItem(CUSTOM_BACKGROUND_STORAGE_KEY) || MICA_BACKGROUND_PRESETS[3]?.url || null;
    } catch {
      return backgroundUrl && backgroundUrl !== "custom" ? backgroundUrl : MICA_BACKGROUND_PRESETS[3]?.url ?? null;
    }
  }

  const preset = MICA_BACKGROUND_PRESETS.find((item) => item.id === backgroundId);
  return preset?.url ?? MICA_BACKGROUND_PRESETS[3]?.url ?? null;
}
